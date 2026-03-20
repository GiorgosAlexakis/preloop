package cmd

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	json5 "github.com/yosuke-furukawa/json5/encoding/json5"

	"github.com/preloop/preloop/cli/internal/api"
)

const (
	openClawManagedProviderID = "preloop"
	openClawGatewayPath       = "/openai/v1"
)

var openClawEnvPattern = regexp.MustCompile(`^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$`)

type managedEnrollmentOptions struct {
	Client           *api.Client
	DryRun           bool
	AutoApprove      bool
	LiveValidate     bool
	SkipConfirmation bool
	Input            io.Reader
	Output           io.Writer
}

type managedLiveValidationOutcome struct {
	Attempted        bool
	Passed           bool
	ValidationResult map[string]interface{}
}

type gatewayUsageSearchResponse struct {
	Items []gatewayUsageSearchItem `json:"items"`
}

type gatewayUsageSearchItem struct {
	APIUsageID         string `json:"api_usage_id"`
	Timestamp          string `json:"timestamp"`
	StatusCode         int    `json:"status_code"`
	ModelAlias         string `json:"model_alias"`
	RuntimePrincipalID string `json:"runtime_principal_id"`
	APIKeyID           string `json:"api_key_id"`
}

type aiModelResponse struct {
	ID              string                 `json:"id"`
	Name            string                 `json:"name"`
	ProviderName    string                 `json:"provider_name"`
	ModelIdentifier string                 `json:"model_identifier"`
	APIEndpoint     string                 `json:"api_endpoint"`
	MetaData        map[string]interface{} `json:"meta_data"`
	HasAPIKey       bool                   `json:"has_api_key"`
}

type aiModelCreateRequest struct {
	Name            string                 `json:"name"`
	Description     string                 `json:"description,omitempty"`
	ProviderName    string                 `json:"provider_name"`
	ModelIdentifier string                 `json:"model_identifier"`
	APIEndpoint     string                 `json:"api_endpoint,omitempty"`
	APIKey          string                 `json:"api_key,omitempty"`
	MetaData        map[string]interface{} `json:"meta_data,omitempty"`
}

type openClawParsedConfig struct {
	Document        map[string]interface{}
	MCPServers      map[string]MCPDef
	ModelRef        string
	ModelAlias      string
	ModelID         string
	ProviderID      string
	ProviderName    string
	ProviderAPI     string
	ProviderBaseURL string
	ProviderAPIKey  string
	ModelCatalog    map[string]interface{}
	Notes           []string
}

func executeManagedEnrollment(agent AgentConfig, opts managedEnrollmentOptions) error {
	client := opts.Client
	var err error
	input := opts.Input
	if input == nil {
		input = os.Stdin
	}
	output := opts.Output
	if output == nil {
		output = os.Stdout
	}
	if client == nil {
		client, err = api.NewClient(FlagToken, FlagURL)
		if err != nil {
			return fmt.Errorf("failed to create API client: %w", err)
		}
	}
	if !client.IsAuthenticated() {
		return fmt.Errorf("not authenticated - run 'preloop auth login' first")
	}

	agent = normalizeDiscoveredAgent(agent)
	if !opts.SkipConfirmation && !opts.AutoApprove {
		agent, err = prepareAgentForEnrollment(bufio.NewReader(input), output, agent, false)
		if err != nil {
			return err
		}
	}

	syncAgent := prepareAgentForRemoteServerSync(agent, client.BaseURL())

	plan, err := buildManagedMCPEnrollmentPlan(
		agent,
		client.BaseURL(),
		"<token created at apply time>",
	)
	if err != nil {
		return err
	}

	printEnrollmentPlan(plan, opts.DryRun)
	if opts.DryRun {
		fmt.Println("Dry run only: no local files or Preloop account state were changed.")
		return nil
	}

	if !opts.SkipConfirmation && !opts.AutoApprove {
		confirmed, err := confirmAction(
			input,
			output,
			fmt.Sprintf(
				"Apply managed Preloop onboarding for %s? (y/N): ",
				resolveAgentDisplayName(agent),
			),
		)
		if err != nil {
			return fmt.Errorf("failed to read confirmation: %w", err)
		}
		if !confirmed {
			fmt.Println("Aborted without applying onboarding.")
			return nil
		}
	}

	serverSync, err := ensureDiscoveredRemoteServers(client, syncAgent)
	if err != nil {
		return err
	}

	allowedServers := append([]string{}, serverSync.Added...)
	allowedServers = append(allowedServers, serverSync.Reused...)
	_, err = issueRuntimeSessionToken(client, syncAgent, allowedServers)
	if err != nil {
		return fmt.Errorf("failed to bootstrap managed agent identity: %w", err)
	}

	managedAgent, err := getManagedAgentForDiscovered(client, agent)
	if err != nil {
		return err
	}

	credentialResp, err := createDurableManagedCredential(client, managedAgent)
	if err != nil {
		return err
	}

	var aiModelNotes []string
	if strings.EqualFold(strings.TrimSpace(agent.Name), "openclaw") {
		parsed, err := parseOpenClawConfig(agent.ConfigPath)
		if err != nil {
			return err
		}
		gatewayURL, _ := resolveOpenClawGateway(client.BaseURL(), parsed.ProviderName)
		_, aiModelNotes, err = syncOpenClawAIModel(
			client,
			managedAgent,
			agent,
			parsed,
			gatewayURL,
		)
		if err != nil {
			return err
		}
	}

	plan, err = buildManagedMCPEnrollmentPlan(
		agent,
		client.BaseURL(),
		credentialResp.Token,
	)
	if err != nil {
		return err
	}

	originalBytes, err := os.ReadFile(agent.ConfigPath)
	if err != nil {
		return fmt.Errorf("failed to read agent config: %w", err)
	}
	backupState, err := createLocalEnrollmentBackup(agent, originalBytes, plan)
	if err != nil {
		return err
	}
	if err := writeJSONDocument(agent.ConfigPath, plan.ManagedDocument); err != nil {
		return err
	}
	if err := saveLocalEnrollmentState(backupState); err != nil {
		return err
	}

	validationDocument, err := loadAgentConfigDocument(agent)
	if err != nil {
		return fmt.Errorf("failed to validate managed config: %w", err)
	}
	validationResult := managedMCPAdapterForAgent(agent).ValidateManagedConfig(
		validationDocument,
		client.BaseURL(),
	)
	validationResult = mergeStringMaps(
		validationResult,
		defaultManagedLiveValidationResult(agent),
	)

	appliedAt := timeNowUTC()
	enrollment, err := createManagedEnrollmentRecord(
		client,
		managedAgent.ID,
		managedAgentEnrollmentCreateRequest{
			EnrollmentType:   "cli_managed_config",
			AdapterKey:       runtimeSessionSourceTypeForAgent(agent.Name),
			Status:           "applied",
			TargetConfigPath: agent.ConfigPath,
			DiscoveredConfig: plan.SanitizedDiscovered,
			ManagedConfig:    plan.SanitizedManaged,
			BackupMetadata: map[string]interface{}{
				"backup_path":          backupState.BackupPath,
				"runtime_principal_id": backupState.RuntimePrincipalID,
			},
			ValidationResult: validationResult,
			RestoreAvailable: true,
			LastAppliedAt:    &appliedAt,
		},
	)
	if err != nil {
		return err
	}
	backupState.EnrollmentID = enrollment.ID
	if err := saveLocalEnrollmentState(backupState); err != nil {
		return err
	}

	requestedLiveValidation := opts.LiveValidate
	if !requestedLiveValidation && supportsManagedLiveValidation(agent) && !opts.SkipConfirmation && !opts.AutoApprove {
		confirmed, err := confirmActionDefaultYes(
			input,
			output,
			fmt.Sprintf(
				"Run live validation for %s now? (Y/n): ",
				resolveAgentDisplayName(agent),
			),
		)
		if err != nil {
			return fmt.Errorf("failed to read live validation confirmation: %w", err)
		}
		requestedLiveValidation = confirmed
	}

	var liveValidationErr error
	if requestedLiveValidation {
		liveOutcome, err := runManagedAgentLiveValidation(client, agent, validationResult)
		if liveOutcome != nil && len(liveOutcome.ValidationResult) > 0 {
			validationResult = liveOutcome.ValidationResult
		}
		if liveOutcome != nil && liveOutcome.Attempted {
			validationStatus := "validated"
			if !liveOutcome.Passed {
				validationStatus = "validation_failed"
			}
			if _, persistErr := validateManagedEnrollmentRecord(
				client,
				agent,
				enrollment.ID,
				validationResult,
				validationStatus,
			); persistErr != nil {
				return persistErr
			}
		}
		if err != nil {
			liveValidationErr = err
		}
	}

	fmt.Printf("✓ Onboarded %s\n", resolveAgentDisplayName(agent))
	fmt.Printf("  Managed agent: %s (%s)\n", managedAgent.ID, runtimePrincipalIDForAgent(agent))
	if len(serverSync.Added) > 0 {
		fmt.Printf(
			"  Added remote MCP servers: %s\n",
			strings.Join(serverSync.Added, ", "),
		)
	}
	if len(serverSync.ImportedFromCommand) > 0 {
		fmt.Printf(
			"  Imported via command heuristics: %s\n",
			strings.Join(serverSync.ImportedFromCommand, ", "),
		)
	}
	if len(serverSync.Reused) > 0 {
		fmt.Printf(
			"  Reused remote MCP servers: %s\n",
			strings.Join(serverSync.Reused, ", "),
		)
	}
	if len(serverSync.Skipped) > 0 {
		fmt.Printf(
			"  Skipped unsupported local MCP servers: %s\n",
			strings.Join(serverSync.Skipped, ", "),
		)
	}
	for _, warning := range serverSync.Warnings {
		fmt.Printf("  Note: %s\n", warning)
	}
	for _, note := range aiModelNotes {
		fmt.Printf("  Note: %s\n", note)
	}
	fmt.Printf("  Durable credential: %s\n", credentialResp.Credential.Name)
	if plan.ManagedModelAlias != "" {
		fmt.Printf(
			"  Managed model alias: %s/%s\n",
			plan.ManagedProviderName,
			plan.ManagedModelAlias,
		)
	}
	if validationResult["live_validation_status"] != nil {
		fmt.Printf("  Live validation: %v\n", validationResult["live_validation_status"])
	}
	fmt.Printf("  Config updated: %s\n", agent.ConfigPath)
	fmt.Printf("  Backup saved: %s\n", backupState.BackupPath)
	if liveValidationErr != nil {
		fmt.Printf("  Warning: live validation failed: %v\n", liveValidationErr)
		if opts.LiveValidate {
			return fmt.Errorf("managed onboarding applied, but live validation failed: %w", liveValidationErr)
		}
	}
	return nil
}

func supportsManagedLiveValidation(agent AgentConfig) bool {
	return strings.EqualFold(strings.TrimSpace(agent.Name), "openclaw")
}

func defaultManagedLiveValidationResult(agent AgentConfig) map[string]interface{} {
	if supportsManagedLiveValidation(agent) {
		return map[string]interface{}{
			"live_validation_supported": true,
			"live_validation_attempted": false,
			"live_validation_passed":    nil,
			"live_validation_status":    "not_run",
		}
	}
	return map[string]interface{}{
		"live_validation_supported": false,
		"live_validation_attempted": false,
		"live_validation_passed":    nil,
		"live_validation_status":    "unsupported",
	}
}

func confirmActionDefaultYes(reader io.Reader, writer io.Writer, prompt string) (bool, error) {
	input, err := promptForTextInput(bufio.NewReader(reader), writer, prompt)
	if err != nil {
		return false, err
	}
	answer := strings.ToLower(strings.TrimSpace(input))
	return answer == "" || answer == "y" || answer == "yes", nil
}

func runManagedAgentLiveValidation(
	client *api.Client,
	agent AgentConfig,
	existingValidation map[string]interface{},
) (*managedLiveValidationOutcome, error) {
	validationResult := mergeStringMaps(existingValidation, defaultManagedLiveValidationResult(agent))
	if !supportsManagedLiveValidation(agent) {
		return &managedLiveValidationOutcome{
			Attempted:        false,
			Passed:           false,
			ValidationResult: validationResult,
		}, nil
	}
	return runOpenClawLiveValidation(client, agent, validationResult)
}

func runOpenClawLiveValidation(
	client *api.Client,
	agent AgentConfig,
	validationResult map[string]interface{},
) (*managedLiveValidationOutcome, error) {
	detail, err := getManagedAgentDetailForDiscovered(client, agent)
	if err != nil {
		return &managedLiveValidationOutcome{
			Attempted: true,
			Passed:    false,
			ValidationResult: mergeStringMaps(validationResult, map[string]interface{}{
				"live_validation_attempted": true,
				"live_validation_passed":    false,
				"live_validation_status":    "failed",
				"live_validation_error":     err.Error(),
			}),
		}, err
	}

	parsed, err := parseOpenClawConfig(agent.ConfigPath)
	if err != nil {
		return &managedLiveValidationOutcome{
			Attempted: true,
			Passed:    false,
			ValidationResult: mergeStringMaps(validationResult, map[string]interface{}{
				"live_validation_attempted": true,
				"live_validation_passed":    false,
				"live_validation_status":    "failed",
				"live_validation_error":     err.Error(),
			}),
		}, err
	}

	token := strings.TrimSpace(parsed.ProviderAPIKey)
	if token == "" {
		err = fmt.Errorf("managed OpenClaw config does not contain a Preloop gateway token")
		return &managedLiveValidationOutcome{
			Attempted: true,
			Passed:    false,
			ValidationResult: mergeStringMaps(validationResult, map[string]interface{}{
				"live_validation_attempted": true,
				"live_validation_passed":    false,
				"live_validation_status":    "failed",
				"live_validation_error":     err.Error(),
			}),
		}, err
	}

	managedModelAlias := openClawManagedModelAlias(parsed)
	validationToken := fmt.Sprintf("preloop-validation-%d", time.Now().UTC().UnixNano())
	prompt := fmt.Sprintf(
		"Welcome to Preloop. Validation token: %s. Reply with ACK only.",
		validationToken,
	)
	requestPayload := map[string]interface{}{
		"model": managedModelAlias,
		"messages": []map[string]interface{}{
			{
				"role":    "user",
				"content": prompt,
			},
		},
		"temperature": 0,
		"max_tokens":  32,
	}

	gatewayClient := api.NewClientWithToken(client.BaseURL(), token)
	var gatewayResponse map[string]interface{}
	requestErr := gatewayClient.Post(
		"/openai/v1/chat/completions",
		requestPayload,
		&gatewayResponse,
	)
	_ = gatewayResponse

	apiKeyID := mostLikelyManagedAPIKeyID(detail.Credentials)
	searchHit, searchErr := waitForManagedValidationUsage(
		client,
		runtimePrincipalIDForAgent(agent),
		apiKeyID,
		managedModelAlias,
		validationToken,
	)

	passed := requestErr == nil && searchErr == nil && searchHit != nil && searchHit.StatusCode < 400
	result := mergeStringMaps(validationResult, map[string]interface{}{
		"live_validation_attempted":      true,
		"live_validation_passed":         passed,
		"live_validation_status":         "failed",
		"live_validation_token":          validationToken,
		"live_validation_prompt":         prompt,
		"live_validation_model_alias":    managedModelAlias,
		"live_validation_runtime_agent":  resolveAgentDisplayName(agent),
		"live_validation_runtime_source": runtimePrincipalIDForAgent(agent),
	})
	if passed {
		result["live_validation_status"] = "passed"
	}
	if apiKeyID != "" {
		result["live_validation_api_key_id"] = apiKeyID
	}
	if searchHit != nil {
		result["live_validation_request_logged"] = true
		result["live_validation_api_usage_id"] = searchHit.APIUsageID
		result["live_validation_logged_at"] = searchHit.Timestamp
		result["live_validation_status_code"] = searchHit.StatusCode
	} else {
		result["live_validation_request_logged"] = false
	}

	var validationErr error
	if requestErr != nil {
		result["live_validation_error"] = requestErr.Error()
		validationErr = requestErr
	}
	if searchErr != nil {
		result["live_validation_lookup_error"] = searchErr.Error()
		if validationErr == nil {
			validationErr = searchErr
		} else {
			validationErr = fmt.Errorf("%v; %w", validationErr, searchErr)
		}
	}
	if !passed && validationErr == nil {
		validationErr = fmt.Errorf("validation request did not appear in gateway usage")
		result["live_validation_lookup_error"] = validationErr.Error()
	}

	return &managedLiveValidationOutcome{
		Attempted:        true,
		Passed:           passed,
		ValidationResult: result,
	}, validationErr
}

func mostLikelyManagedAPIKeyID(credentials []managedAgentCredentialSummary) string {
	for _, credential := range credentials {
		if strings.EqualFold(strings.TrimSpace(credential.Status), "active") && credential.APIKeyID != "" {
			return credential.APIKeyID
		}
	}
	return ""
}

func waitForManagedValidationUsage(
	client *api.Client,
	runtimePrincipalID string,
	apiKeyID string,
	modelAlias string,
	validationToken string,
) (*gatewayUsageSearchItem, error) {
	deadline := time.Now().Add(15 * time.Second)
	for {
		values := url.Values{}
		values.Set("query", validationToken)
		values.Set("runtime_principal_id", runtimePrincipalID)
		values.Set("limit", "5")
		if apiKeyID != "" {
			values.Set("api_key_id", apiKeyID)
		}
		if modelAlias != "" {
			values.Set("model_alias", modelAlias)
		}
		var response gatewayUsageSearchResponse
		if err := client.Get("/api/v1/account/gateway-usage/search?"+values.Encode(), &response); err == nil {
			for _, item := range response.Items {
				if item.APIUsageID != "" {
					return &item, nil
				}
			}
		}
		if time.Now().After(deadline) {
			return nil, fmt.Errorf("timed out waiting for gateway usage search to index validation token %q", validationToken)
		}
		time.Sleep(1 * time.Second)
	}
}

func prepareAgentForRemoteServerSync(agent AgentConfig, baseURL string) AgentConfig {
	if len(agent.MCPServers) > 0 && !hasOnlyManagedPreloopProxy(agent.MCPServers, baseURL) {
		return agent
	}

	state, err := loadLocalEnrollmentState(agent)
	if err != nil || len(state.DiscoveredConfig) == 0 {
		return agent
	}

	recoveredServers := parseServerMapFromDocument(state.DiscoveredConfig)
	if len(recoveredServers) == 0 {
		return agent
	}

	agent.MCPServers = recoveredServers
	return agent
}

func parseOpenClawMCP(path string) (map[string]MCPDef, error) {
	parsed, err := parseOpenClawConfig(path)
	if err != nil {
		return nil, err
	}
	return parsed.MCPServers, nil
}

func parseOpenClawConfig(path string) (*openClawParsedConfig, error) {
	document, err := loadJSON5Document(path)
	if err != nil {
		return nil, err
	}

	mcpServers := parseServerMapFromDocument(document)
	modelRef := extractOpenClawPrimaryModel(document)
	providerID, modelID := splitOpenClawModelRef(modelRef)
	providerName := inferOpenClawProviderName(providerID, lookupString(document, "models", "providers", providerID, "api"))
	apiKey, resolvedNote := resolveOpenClawProviderAPIKey(document, providerID)
	notes := []string{}
	if resolvedNote != "" {
		notes = append(notes, resolvedNote)
	}

	return &openClawParsedConfig{
		Document:        document,
		MCPServers:      mcpServers,
		ModelRef:        modelRef,
		ModelAlias:      buildOpenClawGatewayAlias(providerID, modelID),
		ModelID:         modelID,
		ProviderID:      providerID,
		ProviderName:    providerName,
		ProviderAPI:     pickOpenClawGatewayAPI(lookupString(document, "models", "providers", providerID, "api")),
		ProviderBaseURL: lookupString(document, "models", "providers", providerID, "baseUrl"),
		ProviderAPIKey:  apiKey,
		ModelCatalog:    findOpenClawModelCatalog(document, providerID, modelID),
		Notes:           notes,
	}, nil
}

func buildOpenClawManagedMCPEnrollmentPlan(
	agent AgentConfig,
	baseURL string,
	token string,
) (managedMCPEnrollmentPlan, error) {
	parsed, err := parseOpenClawConfig(agent.ConfigPath)
	if err != nil {
		return managedMCPEnrollmentPlan{}, fmt.Errorf(
			"failed to parse OpenClaw config: %w",
			err,
		)
	}

	managedDoc, err := deepCopyMap(parsed.Document)
	if err != nil {
		return managedMCPEnrollmentPlan{}, err
	}

	managedServerURL := strings.TrimRight(baseURL, "/") + "/mcp/v1"
	gatewayURL, gatewayAPI := resolveOpenClawGateway(baseURL, parsed.ProviderName)

	mcp := ensureObjectPath(managedDoc, "mcp")
	mcp["servers"] = map[string]interface{}{
		"preloop": openClawManagedMCPAdapter{}.BuildManagedServer(baseURL, token),
	}

	models := ensureObjectPath(managedDoc, "models")
	managedModelRef := ""
	if parsed.ModelAlias != "" {
		models["mode"] = "replace"
		models["providers"] = map[string]interface{}{
			openClawManagedProviderID: buildOpenClawManagedProvider(
				parsed,
				gatewayURL,
				gatewayAPI,
				token,
			),
		}
		managedModelRef = openClawManagedProviderID + "/" + parsed.ModelAlias
		rewriteOpenClawModelTargets(managedDoc, managedModelRef)
	}

	notes := append([]string{}, parsed.Notes...)
	if managedModelRef == "" {
		notes = append(
			notes,
			"OpenClaw config did not declare an active model; MCP was managed but no model rewrite was applied.",
		)
	} else {
		notes = append(
			notes,
			fmt.Sprintf(
				"OpenClaw model traffic will use %s via Preloop's OpenAI-compatible gateway.",
				managedModelRef,
			),
		)
	}

	sanitizedDiscovered, err := deepCopyMap(parsed.Document)
	if err != nil {
		return managedMCPEnrollmentPlan{}, err
	}
	sanitizeConfigSnapshot(sanitizedDiscovered)

	sanitizedManaged, err := deepCopyMap(managedDoc)
	if err != nil {
		return managedMCPEnrollmentPlan{}, err
	}
	sanitizeConfigSnapshot(sanitizedManaged)

	return managedMCPEnrollmentPlan{
		Agent:               agent,
		DiscoveredDocument:  parsed.Document,
		ManagedDocument:     managedDoc,
		SanitizedDiscovered: sanitizedDiscovered,
		SanitizedManaged:    sanitizedManaged,
		ManagedServerName:   "preloop",
		ManagedServerURL:    managedServerURL,
		ManagedModelAlias:   parsed.ModelAlias,
		ManagedProviderName: openClawManagedProviderID,
		Notes:               notes,
	}, nil
}

func buildOpenClawManagedProvider(
	parsed *openClawParsedConfig,
	gatewayURL string,
	gatewayAPI string,
	token string,
) map[string]interface{} {
	modelEntry := map[string]interface{}{
		"id":   parsed.ModelAlias,
		"name": parsed.ModelAlias,
	}
	for key, value := range parsed.ModelCatalog {
		modelEntry[key] = value
	}
	modelEntry["id"] = parsed.ModelAlias
	modelEntry["api"] = gatewayAPI
	if _, ok := modelEntry["name"].(string); !ok {
		modelEntry["name"] = parsed.ModelAlias
	}

	return map[string]interface{}{
		"baseUrl":    gatewayURL,
		"apiKey":     token,
		"api":        gatewayAPI,
		"authHeader": true,
		"models":     []interface{}{modelEntry},
	}
}

func syncOpenClawAIModel(
	client *api.Client,
	managedAgent *managedAgentSummary,
	agent AgentConfig,
	parsed *openClawParsedConfig,
	gatewayURL string,
) (*aiModelResponse, []string, error) {
	managedModelAlias := openClawManagedModelAlias(parsed)
	if client == nil || parsed == nil || managedModelAlias == "" {
		return nil, nil, nil
	}

	var existing []aiModelResponse
	if err := client.Get("/api/v1/ai-models", &existing); err != nil {
		return nil, nil, fmt.Errorf("failed to list AI models: %w", err)
	}

	target := findReusableAIModel(existing, parsed, managedModelAlias)
	upstreamResolved := strings.TrimSpace(parsed.ProviderAPIKey) != ""
	if target != nil && target.HasAPIKey {
		upstreamResolved = true
	}
	metaData := mergeGatewayMetaForAIModel(
		target,
		managedAgent,
		agent,
		gatewayURL,
		managedModelAlias,
		upstreamResolved,
	)
	notes := []string{}
	if parsed.ProviderAPIKey == "" {
		notes = append(
			notes,
			"OpenClaw provider credentials were not resolved automatically; verify the imported Preloop AI model has working upstream credentials.",
		)
	}

	if target != nil {
		update := map[string]interface{}{}
		if parsed.ProviderBaseURL != "" && parsed.ProviderBaseURL != target.APIEndpoint {
			update["api_endpoint"] = parsed.ProviderBaseURL
		}
		if !equalJSONMap(target.MetaData, metaData) {
			update["meta_data"] = metaData
		}
		if !target.HasAPIKey && parsed.ProviderAPIKey != "" {
			update["api_key"] = parsed.ProviderAPIKey
		}
		if len(update) > 0 {
			var updated aiModelResponse
			if err := client.Put("/api/v1/ai-models/"+target.ID, update, &updated); err != nil {
				return nil, nil, fmt.Errorf("failed to update AI model %q: %w", target.Name, err)
			}
			target = &updated
			notes = append(
				notes,
				fmt.Sprintf("Updated AI model %q for gateway alias %s.", target.Name, managedModelAlias),
			)
		} else {
			notes = append(
				notes,
				fmt.Sprintf("Reused existing AI model %q for gateway alias %s.", target.Name, managedModelAlias),
			)
		}
		return target, notes, nil
	}

	create := aiModelCreateRequest{
		Name:            fmt.Sprintf("OpenClaw %s", managedModelAlias),
		Description:     "Imported from OpenClaw managed onboarding",
		ProviderName:    parsed.ProviderName,
		ModelIdentifier: parsed.ModelID,
		APIEndpoint:     parsed.ProviderBaseURL,
		APIKey:          parsed.ProviderAPIKey,
		MetaData:        metaData,
	}

	var created aiModelResponse
	if err := client.Post("/api/v1/ai-models", create, &created); err != nil {
		return nil, nil, fmt.Errorf("failed to create AI model for %s: %w", managedModelAlias, err)
	}
	notes = append(
		notes,
		fmt.Sprintf("Imported AI model %q for gateway alias %s.", created.Name, managedModelAlias),
	)
	return &created, notes, nil
}

func findReusableAIModel(
	models []aiModelResponse,
	parsed *openClawParsedConfig,
	managedModelAlias string,
) *aiModelResponse {
	for i := range models {
		if gatewayAliasForAIModel(models[i]) == managedModelAlias {
			return &models[i]
		}
	}
	for i := range models {
		if models[i].ProviderName != parsed.ProviderName {
			continue
		}
		if models[i].ModelIdentifier != parsed.ModelID {
			continue
		}
		if strings.TrimSpace(models[i].APIEndpoint) != strings.TrimSpace(parsed.ProviderBaseURL) {
			continue
		}
		return &models[i]
	}
	return nil
}

func mergeGatewayMetaForAIModel(
	current *aiModelResponse,
	managedAgent *managedAgentSummary,
	agent AgentConfig,
	gatewayURL string,
	managedModelAlias string,
	gatewayEnabled bool,
) map[string]interface{} {
	meta := map[string]interface{}{}
	if current != nil && current.MetaData != nil {
		cloned, err := deepCopyMap(current.MetaData)
		if err == nil {
			meta = cloned
		}
	}
	gateway := map[string]interface{}{
		// Only enable when upstream provider credentials are stored on the
		// AIModel; otherwise the gateway returns "Model credentials are not configured".
		"enabled":          gatewayEnabled,
		"url":              gatewayURL,
		"provider_adapter": "preloop",
		"model_alias":      managedModelAlias,
	}
	meta["gateway"] = gateway
	meta["managed_by"] = "preloop agents onboard openclaw"
	meta["source_agent"] = "openclaw"
	if managedAgent != nil {
		meta["managed_agent_id"] = managedAgent.ID
		meta["managed_agent_session_source_type"] = managedAgent.SessionSourceType
	}
	meta["managed_agent_display_name"] = resolveAgentDisplayName(agent)
	meta["managed_agent_runtime_principal_id"] = runtimePrincipalIDForAgent(agent)
	return meta
}

func openClawManagedModelAlias(parsed *openClawParsedConfig) string {
	if parsed == nil {
		return ""
	}
	if strings.EqualFold(strings.TrimSpace(parsed.ProviderID), openClawManagedProviderID) {
		return strings.TrimSpace(parsed.ModelRef)
	}
	return strings.TrimSpace(openClawManagedProviderID + "/" + parsed.ModelAlias)
}

func gatewayAliasForAIModel(model aiModelResponse) string {
	gateway, ok := asObjectMap(model.MetaData["gateway"])
	if !ok {
		return ""
	}
	alias, _ := gateway["model_alias"].(string)
	return alias
}

func loadAgentConfigDocument(agent AgentConfig) (map[string]interface{}, error) {
	if strings.EqualFold(strings.TrimSpace(agent.Name), "openclaw") {
		return loadJSON5Document(agent.ConfigPath)
	}
	return loadJSONDocument(agent.ConfigPath)
}

func loadJSON5Document(path string) (map[string]interface{}, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var doc map[string]interface{}
	if err := json5.Unmarshal(data, &doc); err != nil {
		return nil, err
	}
	return doc, nil
}

func parseServerMapFromDocument(document map[string]interface{}) map[string]MCPDef {
	container := lookupMCPServerContainer(document)
	result := make(map[string]MCPDef, len(container))
	for name, raw := range container {
		object, ok := asObjectMap(raw)
		if !ok {
			continue
		}
		data, err := json.Marshal(object)
		if err != nil {
			continue
		}
		var def MCPDef
		if err := json.Unmarshal(data, &def); err != nil {
			continue
		}
		result[name] = def
	}
	return result
}

func configPathsForAgentSpec(home string, spec agentSpec) []string {
	seen := map[string]struct{}{}
	var paths []string
	addPath := func(path string) {
		cleaned := expandAgentConfigPath(home, path)
		if cleaned == "" {
			return
		}
		if _, ok := seen[cleaned]; ok {
			return
		}
		seen[cleaned] = struct{}{}
		paths = append(paths, cleaned)
	}

	for _, relPath := range spec.ConfigPaths {
		addPath(filepath.Join(home, relPath))
	}

	if strings.EqualFold(spec.Name, "OpenClaw") {
		for _, path := range openClawConfigPaths(home) {
			addPath(path)
		}
	}

	return paths
}

func openClawConfigPaths(home string) []string {
	configNames := []string{
		"openclaw.json",
		"openclaw.json5",
		"config.json",
		"config.json5",
	}
	baseDirs := []string{
		filepath.Join(home, ".openclaw"),
		filepath.Join(home, ".config", "openclaw"),
	}
	for _, envName := range []string{
		"OPENCLAW_HOME",
		"OPENCLAW_STATE_DIR",
		"OPENCLAW_CONFIG_DIR",
	} {
		if root := expandAgentConfigPath(home, os.Getenv(envName)); root != "" {
			baseDirs = append(baseDirs, root)
		}
	}

	paths := []string{
		expandAgentConfigPath(home, os.Getenv("OPENCLAW_CONFIG_PATH")),
	}
	for _, baseDir := range baseDirs {
		for _, configName := range configNames {
			paths = append(paths, filepath.Join(baseDir, configName))
		}
	}
	return paths
}

func expandAgentConfigPath(home string, path string) string {
	trimmed := strings.TrimSpace(path)
	if trimmed == "" {
		return ""
	}
	if strings.HasPrefix(trimmed, "~/") {
		return filepath.Join(home, trimmed[2:])
	}
	return trimmed
}

func buildManagedRemoteServerRequest(
	name string,
	server MCPDef,
) (map[string]interface{}, string, string, bool) {
	targetURL := strings.TrimSpace(server.URL)
	importMode := "direct"
	warning := ""

	if targetURL == "" {
		inferredURL := extractURLFromCommandBackedServer(server)
		if inferredURL == "" {
			if isLikelyMCporterBackedServer(server) {
				warning = fmt.Sprintf(
					"MCP server %q looks mcporter-backed; skipped because no upstream URL could be inferred safely.",
					name,
				)
			}
			return nil, warning, "", false
		}
		targetURL = inferredURL
		importMode = "command"
		if isLikelyMCporterBackedServer(server) {
			warning = fmt.Sprintf(
				"MCP server %q was imported from a command-based mcporter-style entry using inferred URL %s.",
				name,
				targetURL,
			)
		}
	}

	request := map[string]interface{}{
		"name":      name,
		"url":       targetURL,
		"transport": normalizeDiscoveredTransport(server),
	}
	if importMode == "command" && request["transport"] == "stdio" {
		request["transport"] = "http-streaming"
	}
	authType, authConfig := authConfigForDiscoveredServer(server)
	if authType != "" {
		request["auth_type"] = authType
	}
	if len(authConfig) > 0 {
		request["auth_config"] = authConfig
	}
	return request, warning, importMode, true
}

func hasOnlyManagedPreloopProxy(servers map[string]MCPDef, baseURL string) bool {
	if len(servers) == 0 {
		return false
	}
	for name, server := range servers {
		if !isManagedPreloopProxy(name, server, baseURL) {
			return false
		}
	}
	return true
}

func isManagedPreloopProxy(name string, server MCPDef, baseURL string) bool {
	if !strings.EqualFold(strings.TrimSpace(name), "preloop") {
		return false
	}
	expectedURL := strings.TrimRight(baseURL, "/") + "/mcp/v1"
	return strings.TrimRight(strings.TrimSpace(server.URL), "/") == expectedURL
}

func extractURLFromCommandBackedServer(server MCPDef) string {
	for _, value := range append([]string{server.Command}, server.Args...) {
		if parsed := firstURLFromText(value); parsed != "" {
			return parsed
		}
	}
	for _, value := range server.Env {
		if parsed := firstURLFromText(value); parsed != "" {
			return parsed
		}
	}
	return ""
}

func firstURLFromText(value string) string {
	for _, field := range strings.Fields(value) {
		candidate := strings.Trim(field, "\"'")
		if strings.HasPrefix(candidate, "--url=") {
			candidate = strings.TrimPrefix(candidate, "--url=")
		}
		if strings.HasPrefix(candidate, "http://") || strings.HasPrefix(candidate, "https://") {
			if parsed, err := url.Parse(candidate); err == nil && parsed.Host != "" {
				return candidate
			}
		}
	}
	return ""
}

func isLikelyMCporterBackedServer(server MCPDef) bool {
	text := strings.ToLower(server.Command + " " + strings.Join(server.Args, " "))
	return strings.Contains(text, "mcporter") ||
		strings.Contains(text, "mcp-remote") ||
		strings.Contains(text, "supergateway")
}

func extractOpenClawPrimaryModel(document map[string]interface{}) string {
	for _, path := range [][]string{
		{"agents", "defaults", "model"},
		{"agent", "model"},
	} {
		current := lookupValue(document, path...)
		switch typed := current.(type) {
		case string:
			if strings.TrimSpace(typed) != "" {
				return strings.TrimSpace(typed)
			}
		case map[string]interface{}:
			if primary, _ := typed["primary"].(string); strings.TrimSpace(primary) != "" {
				return strings.TrimSpace(primary)
			}
		}
	}
	return ""
}

func splitOpenClawModelRef(modelRef string) (string, string) {
	trimmed := strings.TrimSpace(modelRef)
	if trimmed == "" {
		return "", ""
	}
	parts := strings.SplitN(trimmed, "/", 2)
	if len(parts) == 1 {
		return "anthropic", trimmed
	}
	return strings.ToLower(strings.TrimSpace(parts[0])), strings.TrimSpace(parts[1])
}

func buildOpenClawGatewayAlias(providerID, modelID string) string {
	if providerID == "" {
		return modelID
	}
	if modelID == "" {
		return providerID
	}
	return providerID + "/" + modelID
}

func inferOpenClawProviderName(providerID, api string) string {
	switch strings.ToLower(strings.TrimSpace(providerID)) {
	case "anthropic":
		return "anthropic"
	case "google", "gemini":
		return "google"
	case "openai":
		return "openai"
	}
	if trimmedProvider := strings.ToLower(strings.TrimSpace(providerID)); trimmedProvider != "" {
		return trimmedProvider
	}
	switch strings.TrimSpace(api) {
	case "anthropic-messages":
		return "anthropic"
	case "google-generative-ai":
		return "google"
	case "openai-completions", "openai-responses":
		return "openai"
	default:
		return "openai"
	}
}

func pickOpenClawGatewayAPI(sourceAPI string) string {
	switch strings.TrimSpace(sourceAPI) {
	case "openai-completions", "openai-responses":
		return strings.TrimSpace(sourceAPI)
	default:
		return "openai-responses"
	}
}

func resolveOpenClawGateway(baseURL string, providerName string) (string, string) {
	// Native OpenAI transport handles most tool calls well, but OpenClaw's OpenAI
	// implementation exits early on Gemini models passing through LiteLLM gateways
	// due to divergent stop-reasons. The Anthropic transport processes it robustly.
	if providerName == "google" || providerName == "gemini" {
		return strings.TrimRight(baseURL, "/") + "/anthropic/v1", "anthropic"
	}
	return strings.TrimRight(baseURL, "/") + "/openai/v1", "openai-responses"
}

func resolveOpenClawProviderAPIKey(
	document map[string]interface{},
	providerID string,
) (string, string) {
	value := lookupValue(document, "models", "providers", providerID, "apiKey")
	if value == nil {
		return resolveOpenClawProfileBackedAPIKey(document, providerID)
	}
	switch typed := value.(type) {
	case string:
		matches := openClawEnvPattern.FindStringSubmatch(strings.TrimSpace(typed))
		if len(matches) == 2 {
			if resolved := strings.TrimSpace(os.Getenv(matches[1])); resolved != "" {
				return resolved, fmt.Sprintf(
					"Resolved OpenClaw provider API key from environment variable %s.",
					matches[1],
				)
			}
			return "", fmt.Sprintf(
				"OpenClaw provider API key references %s, but it is not set in this shell.",
				matches[1],
			)
		}
		return strings.TrimSpace(typed), ""
	case map[string]interface{}:
		if source, _ := typed["source"].(string); source == "env" {
			if id, _ := typed["id"].(string); strings.TrimSpace(id) != "" {
				if resolved := strings.TrimSpace(os.Getenv(id)); resolved != "" {
					return resolved, fmt.Sprintf(
						"Resolved OpenClaw provider API key from SecretRef env %s.",
						id,
					)
				}
				return "", fmt.Sprintf(
					"OpenClaw provider SecretRef env %s is not set in this shell.",
					id,
				)
			}
		}
	}
	return "", "OpenClaw provider API key could not be resolved automatically."
}

// extractOpenClawProfileAPIKeyMaterial reads inline API key material from OpenClaw
// auth.profiles when mode is "api_key" (common for Gemini / Google AI Studio keys).
func extractOpenClawProfileAPIKeyMaterial(profile map[string]interface{}) (string, string) {
	candidates := []string{
		getStringField(profile, "apiKey"),
		getStringField(profile, "api_key"),
	}
	if creds, ok := asObjectMap(profile["credentials"]); ok {
		candidates = append(
			candidates,
			getStringField(creds, "apiKey"),
			getStringField(creds, "api_key"),
		)
	}
	for _, raw := range candidates {
		if key, note := resolveOpenClawInlineAPIKeyString(raw); key != "" {
			return key, note
		}
	}
	return "", ""
}

func getStringField(object map[string]interface{}, key string) string {
	if object == nil {
		return ""
	}
	value, _ := object[key].(string)
	return strings.TrimSpace(value)
}

func resolveOpenClawInlineAPIKeyString(raw string) (string, string) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return "", ""
	}
	matches := openClawEnvPattern.FindStringSubmatch(raw)
	if len(matches) == 2 {
		if resolved := strings.TrimSpace(os.Getenv(matches[1])); resolved != "" {
			return resolved, fmt.Sprintf(
				"Resolved OpenClaw profile API key from environment variable %s.",
				matches[1],
			)
		}
		return "", fmt.Sprintf(
			"OpenClaw profile API key references %s, but it is not set in this shell.",
			matches[1],
		)
	}
	return raw, ""
}

func resolveOpenClawProfileBackedAPIKey(
	document map[string]interface{},
	providerID string,
) (string, string) {
	if strings.TrimSpace(providerID) == "" {
		return "", ""
	}
	for _, profileName := range []string{
		providerID + ":default",
		providerID,
	} {
		profile, ok := asObjectMap(lookupValue(document, "auth", "profiles", profileName))
		if !ok {
			continue
		}
		if mode, _ := profile["mode"].(string); strings.EqualFold(strings.TrimSpace(mode), "api_key") {
			if key, note := extractOpenClawProfileAPIKeyMaterial(profile); key != "" {
				return key, note
			}
			return "", fmt.Sprintf(
				"OpenClaw provider %s uses auth.profiles (%s) for credentials; set an apiKey on the provider block or add the API key in the Preloop console for this model.",
				providerID,
				profileName,
			)
		}
	}
	return "", ""
}

func findOpenClawModelCatalog(
	document map[string]interface{},
	providerID string,
	modelID string,
) map[string]interface{} {
	raw := lookupValue(document, "models", "providers", providerID, "models")
	models, ok := raw.([]interface{})
	if !ok {
		return nil
	}
	for _, item := range models {
		object, ok := asObjectMap(item)
		if !ok {
			continue
		}
		if id, _ := object["id"].(string); id == modelID {
			copied, err := deepCopyMap(object)
			if err == nil {
				return copied
			}
		}
	}
	return nil
}

func rewriteOpenClawModelTargets(document map[string]interface{}, managedModelRef string) {
	rewriteOpenClawModelSelector(document, managedModelRef, "agent")
	rewriteOpenClawModelSelector(document, managedModelRef, "agents", "defaults")

	agentsList, ok := lookupValue(document, "agents", "list").([]interface{})
	if ok {
		for _, item := range agentsList {
			entry, ok := asObjectMap(item)
			if !ok {
				continue
			}
			rewriteOpenClawModelSelector(entry, managedModelRef)
		}
	}

	for _, path := range [][]string{
		{"agent", "models"},
		{"agents", "defaults", "models"},
	} {
		if container, ok := asObjectMap(lookupValue(document, path...)); ok {
			clearMap(container)
			container[managedModelRef] = map[string]interface{}{
				"alias": managedModelRef,
			}
		}
	}
}

func rewriteOpenClawModelSelector(
	root map[string]interface{},
	managedModelRef string,
	path ...string,
) {
	container, ok := lookupValue(root, path...).(map[string]interface{})
	if !ok {
		return
	}
	current := container["model"]
	switch typed := current.(type) {
	case string:
		container["model"] = managedModelRef
	case map[string]interface{}:
		typed["primary"] = managedModelRef
		delete(typed, "fallbacks")
	}
}

func lookupValue(root map[string]interface{}, path ...string) interface{} {
	current := interface{}(root)
	for _, key := range path {
		object, ok := asObjectMap(current)
		if !ok {
			return nil
		}
		current = object[key]
	}
	return current
}

func lookupString(root map[string]interface{}, path ...string) string {
	value, _ := lookupValue(root, path...).(string)
	return strings.TrimSpace(value)
}

func ensureObjectPath(root map[string]interface{}, path ...string) map[string]interface{} {
	current := root
	for _, key := range path {
		if next, ok := asObjectMap(current[key]); ok {
			current = next
			continue
		}
		created := make(map[string]interface{})
		current[key] = created
		current = created
	}
	return current
}

func clearMap(value map[string]interface{}) {
	for key := range value {
		delete(value, key)
	}
}

func equalJSONMap(left, right map[string]interface{}) bool {
	leftBytes, leftErr := json.Marshal(left)
	rightBytes, rightErr := json.Marshal(right)
	if leftErr != nil || rightErr != nil {
		return false
	}
	return string(leftBytes) == string(rightBytes)
}

func timeNowUTC() time.Time {
	return time.Now().UTC()
}
