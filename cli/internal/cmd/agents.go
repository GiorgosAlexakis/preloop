package cmd

import (
	"crypto/sha1"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/user"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/spf13/cobra"

	"github.com/preloop/preloop/cli/internal/api"
	"github.com/preloop/preloop/cli/internal/config"
)

// AgentConfig describes a discovered AI agent MCP configuration.
type AgentConfig struct {
	Name       string            `json:"name"`
	ConfigPath string            `json:"config_path"`
	MCPServers map[string]MCPDef `json:"mcp_servers,omitempty"`
}

// MCPDef is a minimal MCP server definition read from an agent config.
type MCPDef struct {
	Command   string                 `json:"command,omitempty"`
	Args      []string               `json:"args,omitempty"`
	URL       string                 `json:"url,omitempty"`
	Transport string                 `json:"transport,omitempty"`
	Env       map[string]string      `json:"env,omitempty"`
	Headers   map[string]string      `json:"headers,omitempty"`
	Auth      map[string]interface{} `json:"auth,omitempty"`
}

// agentSpec defines where to look for a particular AI agent.
type agentSpec struct {
	Name        string
	ConfigPaths []string // relative to $HOME
	Parser      func(path string) (map[string]MCPDef, error)
}

var agentSpecs = []agentSpec{
	{
		Name:        "Claude Code",
		ConfigPaths: []string{".claude/mcp-servers.json", ".claude/claude_desktop_config.json", ".config/claude/claude_desktop_config.json"},
		Parser:      parseClaudeConfig,
	},
	{
		Name:        "Cursor",
		ConfigPaths: []string{".cursor/mcp.json"},
		Parser:      parseGenericMCP,
	},
	{
		Name:        "Windsurf",
		ConfigPaths: []string{".codeium/windsurf/mcp_config.json"},
		Parser:      parseGenericMCP,
	},
	{
		Name:        "VSCode / Copilot",
		ConfigPaths: []string{".vscode/mcp.json"},
		Parser:      parseGenericMCP,
	},
	{
		Name:        "Gemini CLI",
		ConfigPaths: []string{".gemini/settings.json"},
		Parser:      parseGeminiConfig,
	},
	{
		Name:        "OpenCode",
		ConfigPaths: []string{".config/opencode/config.json"},
		Parser:      parseGenericMCP,
	},
	{
		Name:        "Codex CLI",
		ConfigPaths: []string{".codex/config.json"},
		Parser:      parseGenericMCP,
	},
	{
		Name: "OpenClaw",
		ConfigPaths: []string{
			".openclaw/openclaw.json",
			".openclaw/openclaw.json5",
			".openclaw-dev/openclaw.json",
			".openclaw-dev/openclaw.json5",
		},
		Parser: parseOpenClawMCP,
	},
}

// agentsCmd is the top-level agent management command.
var agentsCmd = &cobra.Command{
	Use:   "agents",
	Short: "Manage AI agents",
	Long:  `Discover and manage AI agents configured on your machine.`,
}

// agentsDiscoverCmd scans for local AI agents.
var agentsDiscoverCmd = &cobra.Command{
	Use:   "discover",
	Short: "Discover AI agents on this machine",
	Long: `Scan standard configuration paths for known AI agents and display their
MCP server configurations without mutating local files or your Preloop account.

Supported agents: Claude Code, Cursor, Windsurf, VSCode/Copilot,
                  Gemini CLI, OpenCode, Codex CLI, OpenClaw.

Examples:
  preloop agents discover
  preloop agents discover --json`,
	RunE: runAgentsDiscover,
}

var agentsEnrollCmd = &cobra.Command{
	Use:   "enroll <agent>",
	Short: "Enroll a discovered agent into managed MCP access",
	Long: `Create or locate the managed agent identity in Preloop, create a durable
credential for it, back up the local config, and add a managed Preloop MCP server
entry to the selected agent configuration.

This is the mutating companion to 'preloop agents discover'. Use --dry-run to
preview the planned config and account changes without writing anything.`,
	Args: cobra.ExactArgs(1),
	RunE: runAgentsEnroll,
}

var agentsStatusCmd = &cobra.Command{
	Use:   "status <agent>",
	Short: "Show managed enrollment status for an agent",
	Args:  cobra.ExactArgs(1),
	RunE:  runAgentsStatus,
}

var agentsValidateCmd = &cobra.Command{
	Use:   "validate <agent>",
	Short: "Validate managed enrollment for an agent",
	Args:  cobra.ExactArgs(1),
	RunE:  runAgentsValidate,
}

var agentsRestoreCmd = &cobra.Command{
	Use:   "restore <agent>",
	Short: "Restore the most recent local backup for an enrolled agent",
	Args:  cobra.ExactArgs(1),
	RunE:  runAgentsRestore,
}

type starterPolicyTool struct {
	Name                 string                    `json:"name"`
	Description          string                    `json:"description,omitempty"`
	Source               string                    `json:"source"`
	SourceID             string                    `json:"source_id,omitempty"`
	SourceName           string                    `json:"source_name,omitempty"`
	Schema               map[string]interface{}    `json:"schema,omitempty"`
	IsEnabled            bool                      `json:"is_enabled"`
	HasApprovalCondition bool                      `json:"has_approval_condition"`
	AccessRules          []starterPolicyAccessRule `json:"access_rules,omitempty"`
}

type starterPolicyAccessRule struct {
	Action             string `json:"action"`
	ConditionType      string `json:"condition_type,omitempty"`
	Description        string `json:"description,omitempty"`
	ApprovalWorkflowID string `json:"approval_workflow_id,omitempty"`
}

type runtimeSessionTokenRequest struct {
	SessionSourceType    string   `json:"session_source_type"`
	SessionSourceID      string   `json:"session_source_id"`
	SessionReference     string   `json:"session_reference,omitempty"`
	RuntimePrincipalID   string   `json:"runtime_principal_id,omitempty"`
	RuntimePrincipalName string   `json:"runtime_principal_name,omitempty"`
	ExpiresInMinutes     int      `json:"expires_in_minutes,omitempty"`
	Scopes               []string `json:"scopes,omitempty"`
	AllowedMCPServers    []string `json:"allowed_mcp_servers,omitempty"`
}

type runtimeSessionTokenResponse struct {
	RuntimeSessionID  string `json:"runtime_session_id"`
	Token             string `json:"token"`
	ExpiresAt         string `json:"expires_at"`
	SessionSourceType string `json:"session_source_type"`
	SessionSourceID   string `json:"session_source_id"`
	SessionReference  string `json:"session_reference,omitempty"`
}

type mcpServerResponse struct {
	ID         string                 `json:"id"`
	Name       string                 `json:"name"`
	URL        string                 `json:"url"`
	Transport  string                 `json:"transport,omitempty"`
	AuthType   string                 `json:"auth_type,omitempty"`
	AuthConfig map[string]interface{} `json:"auth_config,omitempty"`
}

type managedAgentSummary struct {
	ID                string   `json:"id"`
	DisplayName       string   `json:"display_name"`
	SessionSourceType string   `json:"session_source_type"`
	SessionSourceID   string   `json:"session_source_id"`
	SessionReference  string   `json:"session_reference,omitempty"`
	LifecycleState    string   `json:"lifecycle_state"`
	ManagedMCPServers []string `json:"managed_mcp_servers"`
}

type managedAgentListResponse struct {
	Items []managedAgentSummary `json:"items"`
}

type managedAgentCredentialSummary struct {
	ID            string `json:"id"`
	Name          string `json:"name"`
	Status        string `json:"status"`
	KeyPrefix     string `json:"key_prefix,omitempty"`
	CreatedAt     string `json:"created_at"`
	RevokedAt     string `json:"revoked_at,omitempty"`
	RevokedReason string `json:"revoked_reason,omitempty"`
}

type managedAgentCredentialCreateRequest struct {
	Name          string   `json:"name"`
	Description   string   `json:"description,omitempty"`
	ExpiresInDays int      `json:"expires_in_days,omitempty"`
	Scopes        []string `json:"scopes,omitempty"`
}

type managedAgentCredentialCreateResponse struct {
	Credential managedAgentCredentialSummary `json:"credential"`
	Token      string                        `json:"token"`
}

type managedAgentEnrollmentSummary struct {
	ID               string                 `json:"id"`
	EnrollmentType   string                 `json:"enrollment_type"`
	AdapterKey       string                 `json:"adapter_key,omitempty"`
	Status           string                 `json:"status"`
	TargetConfigPath string                 `json:"target_config_path,omitempty"`
	DiscoveredConfig map[string]interface{} `json:"discovered_config,omitempty"`
	ManagedConfig    map[string]interface{} `json:"managed_config,omitempty"`
	BackupMetadata   map[string]interface{} `json:"backup_metadata,omitempty"`
	ValidationResult map[string]interface{} `json:"validation_result,omitempty"`
	RestoreAvailable bool                   `json:"restore_available"`
	CreatedAt        string                 `json:"created_at"`
	UpdatedAt        string                 `json:"updated_at"`
	LastAppliedAt    string                 `json:"last_applied_at,omitempty"`
	LastValidatedAt  string                 `json:"last_validated_at,omitempty"`
	LastRestoredAt   string                 `json:"last_restored_at,omitempty"`
}

type managedAgentEnrollmentCreateRequest struct {
	EnrollmentType   string                 `json:"enrollment_type"`
	AdapterKey       string                 `json:"adapter_key,omitempty"`
	Status           string                 `json:"status"`
	TargetConfigPath string                 `json:"target_config_path,omitempty"`
	DiscoveredConfig map[string]interface{} `json:"discovered_config,omitempty"`
	ManagedConfig    map[string]interface{} `json:"managed_config,omitempty"`
	BackupMetadata   map[string]interface{} `json:"backup_metadata,omitempty"`
	ValidationResult map[string]interface{} `json:"validation_result,omitempty"`
	RestoreAvailable bool                   `json:"restore_available"`
	LastAppliedAt    *time.Time             `json:"last_applied_at,omitempty"`
	LastValidatedAt  *time.Time             `json:"last_validated_at,omitempty"`
	LastRestoredAt   *time.Time             `json:"last_restored_at,omitempty"`
}

type managedAgentDetailResponse struct {
	Agent       managedAgentSummary             `json:"agent"`
	Credentials []managedAgentCredentialSummary `json:"credentials"`
	Enrollments []managedAgentEnrollmentSummary `json:"enrollments"`
}

type managedMCPEnrollmentPlan struct {
	Agent               AgentConfig
	DiscoveredDocument  map[string]interface{}
	ManagedDocument     map[string]interface{}
	SanitizedDiscovered map[string]interface{}
	SanitizedManaged    map[string]interface{}
	ManagedServerName   string
	ManagedServerURL    string
	ManagedModelAlias   string
	ManagedProviderName string
	Notes               []string
}

type remoteServerSyncResult struct {
	Added               []string
	Reused              []string
	Skipped             []string
	ImportedFromCommand []string
	Warnings            []string
}

type localEnrollmentState struct {
	AgentName          string                 `json:"agent_name"`
	RuntimePrincipalID string                 `json:"runtime_principal_id"`
	EnrollmentID       string                 `json:"enrollment_id,omitempty"`
	ConfigPath         string                 `json:"config_path"`
	BackupPath         string                 `json:"backup_path"`
	ManagedServerName  string                 `json:"managed_server_name"`
	ManagedServerURL   string                 `json:"managed_server_url"`
	AppliedAt          time.Time              `json:"applied_at"`
	RestoredAt         *time.Time             `json:"restored_at,omitempty"`
	DiscoveredConfig   map[string]interface{} `json:"discovered_config,omitempty"`
	ManagedConfig      map[string]interface{} `json:"managed_config,omitempty"`
}

type managedMCPAdapter interface {
	Key() string
	EnsureServerContainer(doc map[string]interface{}) (map[string]interface{}, error)
	BuildManagedServer(baseURL, token string) map[string]interface{}
	ValidateManagedConfig(doc map[string]interface{}, baseURL string) map[string]interface{}
}

// agentsStarterPolicyCmd generates a starter policy suggestion for an MCP server.
var agentsStarterPolicyCmd = &cobra.Command{
	Use:   "starter-policy <mcp-server>",
	Short: "Generate a starter policy for an MCP server",
	Long: `Generate a scoped starter policy suggestion for a specific MCP server
using the existing policy generation API.

The generated prompt is limited to the selected server and its discovered tools,
preserves current account configuration, and prefers approvals for mutating or
otherwise high-impact tools.

Examples:
  preloop agents starter-policy github
  preloop agents starter-policy github --output github-policy.yaml
  preloop agents starter-policy github --apply
  preloop agents starter-policy github --apply --yes
  preloop agents starter-policy github --apply --dry-run`,
	Args: cobra.ExactArgs(1),
	RunE: runAgentsStarterPolicy,
}

func init() {
	agentsCmd.AddCommand(agentsDiscoverCmd)
	agentsCmd.AddCommand(agentsEnrollCmd)
	agentsCmd.AddCommand(agentsStatusCmd)
	agentsCmd.AddCommand(agentsValidateCmd)
	agentsCmd.AddCommand(agentsRestoreCmd)
	agentsCmd.AddCommand(agentsStarterPolicyCmd)

	agentsDiscoverCmd.Flags().Bool("add", false, "deprecated: use 'preloop agents enroll <agent>' instead")
	agentsDiscoverCmd.Flags().Bool("json", false, "output discovered agents as JSON")
	agentsDiscoverCmd.Flags().Bool("no-onboard-prompt", false, "do not prompt to onboard discovered agents")
	agentsDiscoverCmd.Flags().Bool("yes", false, "auto-approve interactive onboarding prompts")
	_ = agentsDiscoverCmd.Flags().MarkDeprecated("add", "use 'preloop agents enroll <agent>'")
	agentsEnrollCmd.Flags().Bool("dry-run", false, "preview account and config changes without writing")
	agentsEnrollCmd.Flags().Bool("yes", false, "skip the enrollment confirmation prompt")
	agentsStatusCmd.Flags().Bool("json", false, "output managed status as JSON")
	agentsRestoreCmd.Flags().Bool("yes", false, "skip the restore confirmation prompt")
	agentsStarterPolicyCmd.Flags().StringP("output", "o", "", "write generated policy YAML to a file")
	agentsStarterPolicyCmd.Flags().Bool("apply", false, "apply the generated policy immediately")
	agentsStarterPolicyCmd.Flags().Bool("dry-run", false, "when used with --apply, validate without applying changes")
	agentsStarterPolicyCmd.Flags().Bool("yes", false, "skip the apply confirmation prompt after previewing changes")
	agentsStarterPolicyCmd.Flags().Bool("no-context", false, "do not include current account config as context for the LLM")
}

// runAgentsDiscover scans for AI agents on the machine.
func runAgentsDiscover(cmd *cobra.Command, args []string) error {
	asJSON, _ := cmd.Flags().GetBool("json")
	addServers, _ := cmd.Flags().GetBool("add")
	noOnboardPrompt, _ := cmd.Flags().GetBool("no-onboard-prompt")
	autoApprove, _ := cmd.Flags().GetBool("yes")

	if addServers {
		return fmt.Errorf("discover is now read-only; use 'preloop agents enroll <agent>'")
	}

	discovered, err := discoverAgents(os.Stdout, !asJSON)
	if err != nil {
		return err
	}

	if asJSON {
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		return enc.Encode(discovered)
	}

	if len(discovered) == 0 {
		fmt.Println("No AI agents found on this machine.")
		fmt.Println("Looked for: Claude Code, Cursor, Windsurf, VSCode, Gemini CLI, OpenCode, Codex CLI, OpenClaw")
		return nil
	}

	fmt.Printf("Found %d AI agent(s):\n\n", len(discovered))

	totalServers := 0
	for _, agent := range discovered {
		serverCount := len(agent.MCPServers)
		totalServers += serverCount
		fmt.Printf("  🤖 %s\n", agent.Name)
		fmt.Printf("     Config: %s\n", agent.ConfigPath)
		if serverCount > 0 {
			fmt.Printf("     MCP Servers (%d):\n", serverCount)
			for name := range agent.MCPServers {
				fmt.Printf("       - %s\n", name)
			}
		} else {
			fmt.Println("     No MCP servers configured")
		}
		fmt.Println()
	}

	if totalServers > 0 {
		fmt.Println("Tip: Use 'preloop agents enroll <agent>' to create a managed Preloop MCP entry with backup and restore support.")
	}

	if noOnboardPrompt {
		return nil
	}

	return promptToOnboardDiscoveredAgents(discovered, autoApprove)
}

func promptToOnboardDiscoveredAgents(discovered []AgentConfig, autoApprove bool) error {
	client, err := api.NewClient(FlagToken, FlagURL)
	if err != nil {
		return fmt.Errorf("failed to create API client: %w", err)
	}
	if !client.IsAuthenticated() {
		fmt.Println("Tip: Run 'preloop auth login' to onboard discovered agents.")
		return nil
	}

	candidates, err := filterAgentsPendingEnrollment(client, discovered)
	if err != nil {
		return err
	}
	if len(candidates) == 0 {
		fmt.Println("All discovered agents are already onboarded or have local managed enrollment state.")
		return nil
	}

	for _, agent := range candidates {
		if !autoApprove {
			confirmed, err := confirmAction(
				os.Stdin,
				os.Stdout,
				fmt.Sprintf("Onboard %s into managed Preloop access now? (y/N): ", agent.Name),
			)
			if err != nil {
				return fmt.Errorf("failed to read onboarding confirmation: %w", err)
			}
			if !confirmed {
				continue
			}
		}
		if err := executeManagedEnrollment(agent, managedEnrollmentOptions{
			Client:           client,
			SkipConfirmation: true,
		}); err != nil {
			return err
		}
	}

	return nil
}

func filterAgentsPendingLocalEnrollment(discovered []AgentConfig) []AgentConfig {
	candidates := make([]AgentConfig, 0, len(discovered))
	for _, agent := range discovered {
		if _, err := loadLocalEnrollmentState(agent); err == nil {
			continue
		}
		candidates = append(candidates, agent)
	}
	return candidates
}

func filterAgentsPendingEnrollment(client *api.Client, discovered []AgentConfig) ([]AgentConfig, error) {
	candidates := make([]AgentConfig, 0, len(discovered))
	for _, agent := range discovered {
		if _, err := loadLocalEnrollmentState(agent); err == nil {
			continue
		}
		if client != nil {
			if _, err := getManagedAgentForDiscovered(client, agent); err == nil {
				continue
			}
		}
		candidates = append(candidates, agent)
	}
	return candidates, nil
}

func runAgentsEnroll(cmd *cobra.Command, args []string) error {
	dryRun, _ := cmd.Flags().GetBool("dry-run")
	autoApprove, _ := cmd.Flags().GetBool("yes")

	discovered, err := discoverAgents(os.Stdout, true)
	if err != nil {
		return err
	}
	agent, err := findDiscoveredAgent(discovered, args[0])
	if err != nil {
		return err
	}

	return executeManagedEnrollment(agent, managedEnrollmentOptions{
		DryRun:           dryRun,
		AutoApprove:      autoApprove,
		SkipConfirmation: false,
	})
}

func runAgentsStatus(cmd *cobra.Command, args []string) error {
	asJSON, _ := cmd.Flags().GetBool("json")

	discovered, err := discoverAgents(io.Discard, false)
	if err != nil {
		return err
	}
	agent, err := findDiscoveredAgent(discovered, args[0])
	if err != nil {
		return err
	}

	localState, _ := loadLocalEnrollmentState(agent)
	client, err := api.NewClient(FlagToken, FlagURL)
	if err != nil {
		return fmt.Errorf("failed to create API client: %w", err)
	}

	var detail *managedAgentDetailResponse
	if client.IsAuthenticated() {
		managedAgent, err := getManagedAgentForDiscovered(client, agent)
		if err == nil {
			resp, err := getManagedAgentDetail(client, managedAgent.ID)
			if err != nil {
				return err
			}
			detail = resp
		}
	}

	if asJSON {
		payload := map[string]interface{}{
			"agent":        agent,
			"local_state":  localState,
			"remote_state": detail,
		}
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		return enc.Encode(payload)
	}

	fmt.Printf("Agent: %s\n", agent.Name)
	fmt.Printf("Config: %s\n", agent.ConfigPath)
	fmt.Printf("Runtime principal: %s\n", runtimePrincipalIDForAgent(agent))
	if localState != nil {
		fmt.Printf("Local backup: %s\n", localState.BackupPath)
		fmt.Printf("Managed MCP URL: %s\n", localState.ManagedServerURL)
	}
	if detail == nil {
		if client.IsAuthenticated() {
			fmt.Println("Remote status: managed agent not found yet")
		} else {
			fmt.Println("Remote status: unavailable (not authenticated)")
		}
		return nil
	}

	fmt.Printf("Managed agent ID: %s\n", detail.Agent.ID)
	fmt.Printf("Lifecycle: %s\n", detail.Agent.LifecycleState)
	if len(detail.Agent.ManagedMCPServers) > 0 {
		fmt.Printf("Managed MCP servers: %s\n", strings.Join(detail.Agent.ManagedMCPServers, ", "))
	}
	fmt.Printf("Durable credentials: %d\n", len(detail.Credentials))
	if len(detail.Enrollments) > 0 {
		latest := detail.Enrollments[0]
		fmt.Printf("Latest enrollment: %s (%s)\n", latest.EnrollmentType, latest.Status)
		if latest.TargetConfigPath != "" {
			fmt.Printf("Target config: %s\n", latest.TargetConfigPath)
		}
	}
	return nil
}

func runAgentsValidate(cmd *cobra.Command, args []string) error {
	discovered, err := discoverAgents(io.Discard, false)
	if err != nil {
		return err
	}
	agent, err := findDiscoveredAgent(discovered, args[0])
	if err != nil {
		return err
	}

	result := map[string]interface{}{
		"config_path": agent.ConfigPath,
	}
	status := "validated"
	adapter := managedMCPAdapterForAgent(agent)
	document, err := loadAgentConfigDocument(agent)
	if err != nil {
		status = "validation_failed"
		result["config_parse_ok"] = false
		result["error"] = err.Error()
	} else {
		result["config_parse_ok"] = true
		for key, value := range adapter.ValidateManagedConfig(document, clientBaseURLForFlags()) {
			result[key] = value
		}
		if passed, _ := result["validation_passed"].(bool); !passed {
			status = "validation_failed"
		}
	}

	fmt.Printf("Validation status for %s: %s\n", agent.Name, status)
	for _, key := range []string{"config_path", "config_parse_ok", "preloop_server_present", "error"} {
		if value, ok := result[key]; ok {
			fmt.Printf("  %s: %v\n", key, value)
		}
	}

	client, err := api.NewClient(FlagToken, FlagURL)
	if err == nil && client.IsAuthenticated() {
		enrollmentID := ""
		if state, err := loadLocalEnrollmentState(agent); err == nil {
			enrollmentID = state.EnrollmentID
		}
		if enrollmentID == "" {
			if detail, err := getManagedAgentDetailForDiscovered(client, agent); err == nil {
				for _, enrollment := range detail.Enrollments {
					if enrollment.EnrollmentType == "cli_managed_config" {
						enrollmentID = enrollment.ID
						break
					}
				}
			}
		}
		if enrollmentID != "" {
			if _, err := validateManagedEnrollmentRecord(client, agent, enrollmentID, result, status); err != nil {
				return err
			}
		}
	}

	if status != "validated" {
		return fmt.Errorf("managed enrollment validation failed")
	}
	return nil
}

func runAgentsRestore(cmd *cobra.Command, args []string) error {
	autoApprove, _ := cmd.Flags().GetBool("yes")

	discovered, err := discoverAgents(io.Discard, false)
	if err != nil {
		return err
	}
	agent, err := findDiscoveredAgent(discovered, args[0])
	if err != nil {
		return err
	}

	state, err := loadLocalEnrollmentState(agent)
	if err != nil {
		return err
	}
	if !autoApprove {
		confirmed, err := confirmAction(
			os.Stdin,
			os.Stdout,
			fmt.Sprintf("Restore %s from local backup %s? (y/N): ", agent.Name, state.BackupPath),
		)
		if err != nil {
			return fmt.Errorf("failed to read confirmation: %w", err)
		}
		if !confirmed {
			fmt.Println("Aborted without restoring config.")
			return nil
		}
	}
	backupBytes, err := os.ReadFile(state.BackupPath)
	if err != nil {
		return fmt.Errorf("failed to read backup: %w", err)
	}
	if err := os.WriteFile(agent.ConfigPath, backupBytes, 0644); err != nil {
		return fmt.Errorf("failed to restore config: %w", err)
	}
	now := time.Now().UTC()
	state.RestoredAt = &now
	if err := saveLocalEnrollmentState(state); err != nil {
		return err
	}

	client, err := api.NewClient(FlagToken, FlagURL)
	if err == nil && client.IsAuthenticated() {
		if state.EnrollmentID != "" {
			_, _ = restoreManagedEnrollmentRecord(
				client,
				agent,
				state.EnrollmentID,
				map[string]interface{}{
					"backup_path": state.BackupPath,
				},
			)
		} else if managedAgent, err := getManagedAgentForDiscovered(client, agent); err == nil {
			_, _ = createManagedEnrollmentRecord(client, managedAgent.ID, managedAgentEnrollmentCreateRequest{
				EnrollmentType:   "cli_managed_config_restore",
				AdapterKey:       runtimeSessionSourceTypeForAgent(agent.Name),
				Status:           "restored",
				TargetConfigPath: agent.ConfigPath,
				BackupMetadata: map[string]interface{}{
					"backup_path": state.BackupPath,
				},
				RestoreAvailable: false,
				LastRestoredAt:   &now,
			})
		}
	}

	fmt.Printf("✓ Restored %s config from %s\n", agent.Name, state.BackupPath)
	return nil
}

// addDiscoveredServers interactively adds servers to the Preloop account.
func addDiscoveredServers(agents []AgentConfig) error {
	client, err := api.NewClient(FlagToken, FlagURL)
	if err != nil {
		return fmt.Errorf("failed to create API client: %w", err)
	}

	if !client.IsAuthenticated() {
		return fmt.Errorf("not authenticated - run 'preloop auth login' first")
	}

	currentUser, err := user.Current()
	if err != nil {
		currentUser = &user.User{Username: "unknown"}
	}

	for _, agent := range agents {
		addedServerNames := make([]string, 0, len(agent.MCPServers))
		for _, name := range sortedServerNames(agent.MCPServers) {
			server := agent.MCPServers[name]
			fmt.Printf("Add MCP server '%s' from %s? (y/N): ", name, agent.Name)
			var answer string
			fmt.Scanln(&answer)

			if strings.ToLower(strings.TrimSpace(answer)) != "y" {
				continue
			}

			// Build the request to add the server
			request := map[string]interface{}{
				"name":     name,
				"url":      server.URL,
				"command":  server.Command,
				"args":     server.Args,
				"source":   fmt.Sprintf("discovered:%s", agent.Name),
				"metadata": map[string]string{"discovered_by": currentUser.Username},
			}

			var result struct {
				ID   string `json:"id"`
				Name string `json:"name"`
			}

			if err := client.Post("/api/v1/mcp-servers", request, &result); err != nil {
				fmt.Printf("  ✗ Failed to add '%s': %v\n", name, err)
				continue
			}

			fmt.Printf("  ✓ Added MCP server '%s' (ID: %s)\n", result.Name, result.ID)
			addedServerNames = append(addedServerNames, result.Name)
		}

		if len(addedServerNames) == 0 {
			continue
		}

		fmt.Printf(
			"Issue a runtime session token for %s with %d managed MCP server(s)? (y/N): ",
			agent.Name,
			len(addedServerNames),
		)
		var answer string
		fmt.Scanln(&answer)

		if strings.ToLower(strings.TrimSpace(answer)) != "y" {
			continue
		}

		tokenResult, err := issueRuntimeSessionToken(client, agent, addedServerNames)
		if err != nil {
			fmt.Printf("  ✗ Failed to create runtime session token: %v\n", err)
			continue
		}

		fmt.Printf("  🔑 Runtime Session Token: %s\n", tokenResult.Token)
		fmt.Printf("     Session: %s / %s\n", tokenResult.SessionSourceType, tokenResult.SessionSourceID)
		fmt.Printf("     Runtime session ID: %s\n", tokenResult.RuntimeSessionID)
		if tokenResult.ExpiresAt != "" {
			fmt.Printf("     Expires at: %s\n", tokenResult.ExpiresAt)
		}
		fmt.Println("     Store this token securely — it won't be shown again.")
	}

	return nil
}

func sortedServerNames(servers map[string]MCPDef) []string {
	names := make([]string, 0, len(servers))
	for name := range servers {
		names = append(names, name)
	}
	sort.Strings(names)
	return names
}

func issueRuntimeSessionToken(client *api.Client, agent AgentConfig, allowedServers []string) (*runtimeSessionTokenResponse, error) {
	serverNames := append([]string(nil), allowedServers...)
	sort.Strings(serverNames)

	request := runtimeSessionTokenRequest{
		SessionSourceType:    runtimeSessionSourceTypeForAgent(agent.Name),
		SessionSourceID:      runtimeSessionInstanceIDForAgent(agent),
		SessionReference:     filepath.Clean(agent.ConfigPath),
		RuntimePrincipalID:   runtimePrincipalIDForAgent(agent),
		RuntimePrincipalName: runtimePrincipalNameForAgent(agent),
		ExpiresInMinutes:     120,
		Scopes:               []string{"mcp:read", "mcp:write"},
		AllowedMCPServers:    serverNames,
	}

	var result runtimeSessionTokenResponse
	if err := client.Post("/api/v1/auth/runtime-sessions/token", request, &result); err != nil {
		return nil, err
	}

	return &result, nil
}

func runtimeSessionSourceTypeForAgent(agentName string) string {
	switch strings.ToLower(strings.TrimSpace(agentName)) {
	case "claude code":
		return "claude_code"
	case "claude desktop":
		return "claude_desktop"
	case "codex cli":
		return "codex"
	case "openclaw":
		return "openclaw"
	default:
		return "desktop_agent"
	}
}

func runtimePrincipalIDForAgent(agent AgentConfig) string {
	sum := sha1.Sum([]byte(strings.ToLower(agent.Name) + "\x00" + filepath.Clean(agent.ConfigPath)))
	prefix := strings.ToLower(agent.Name)
	replacer := strings.NewReplacer(" ", "-", "/", "-", "\\", "-", ":", "-", ".", "-")
	prefix = strings.Trim(replacer.Replace(prefix), "-")
	if prefix == "" {
		prefix = "agent"
	}
	return fmt.Sprintf("%s-%s", prefix, hex.EncodeToString(sum[:6]))
}

func runtimeSessionInstanceIDForAgent(agent AgentConfig) string {
	return fmt.Sprintf("%s-%d", runtimePrincipalIDForAgent(agent), time.Now().UnixNano())
}

func runtimePrincipalNameForAgent(agent AgentConfig) string {
	configBase := filepath.Base(filepath.Clean(agent.ConfigPath))
	if configBase == "." || configBase == string(filepath.Separator) || configBase == "" {
		return agent.Name
	}
	return fmt.Sprintf("%s (%s)", agent.Name, configBase)
}

func runAgentsStarterPolicy(cmd *cobra.Command, args []string) error {
	serverName := args[0]
	output, _ := cmd.Flags().GetString("output")
	apply, _ := cmd.Flags().GetBool("apply")
	dryRun, _ := cmd.Flags().GetBool("dry-run")
	autoApprove, _ := cmd.Flags().GetBool("yes")
	noContext, _ := cmd.Flags().GetBool("no-context")

	client, err := api.NewClient(FlagToken, FlagURL)
	if err != nil {
		return fmt.Errorf("failed to create API client: %w", err)
	}

	if !client.IsAuthenticated() {
		return fmt.Errorf("not authenticated - run 'preloop auth login' first")
	}

	matchedServerName, tools, err := findStarterPolicyTools(client, serverName)
	if err != nil {
		return err
	}

	fmt.Printf(
		"Generating starter policy for MCP server '%s' (%d discovered tool(s))...\n",
		matchedServerName,
		len(tools),
	)

	prompt := buildStarterPolicyPrompt(matchedServerName, tools)
	result, err := generatePolicyFromPrompt(client, prompt, !noContext)
	if err != nil {
		return fmt.Errorf("failed to generate starter policy: %w", err)
	}

	printPolicyWarnings(result.Warnings)

	fileName := defaultStarterPolicyFileName(matchedServerName)
	if output != "" {
		if err := os.WriteFile(output, []byte(result.YAML), 0644); err != nil {
			return fmt.Errorf("failed to write generated policy: %w", err)
		}
		fmt.Printf("✓ Generated policy written to: %s\n", output)
	} else {
		fmt.Println("\n---")
		fmt.Print(result.YAML)
		fmt.Println("---")
	}

	diff, err := diffPolicyContent(client, fileName, []byte(result.YAML))
	if err != nil {
		return fmt.Errorf("failed to preview generated policy diff: %w", err)
	}
	printPolicyDiffPreview(diff)

	if !apply {
		if output == "" {
			fmt.Println("\nTip: Review the diff above, then use --apply to apply it immediately or -o policy.yaml to save it.")
		}
		return nil
	}

	if !diff.HasChanges {
		fmt.Println("Generated policy already matches the current configuration. Nothing to apply.")
		return nil
	}

	if dryRun {
		fmt.Println("\nValidating generated policy with the server (dry run)...")
	} else {
		_, _, removed := splitPolicyDiffChanges(diff)
		fmt.Println("\nReview changes above carefully. Applying will update your active Preloop policy.")
		if len(removed) > 0 {
			fmt.Printf("Warning: %d existing item(s) will be removed if you continue.\n", len(removed))
		}
		if !autoApprove {
			confirmed, err := confirmAction(os.Stdin, os.Stdout, buildPolicyApplyConfirmationPrompt(diff))
			if err != nil {
				return fmt.Errorf("failed to read confirmation: %w", err)
			}
			if !confirmed {
				fmt.Println("Aborted without applying changes.")
				return nil
			}
		}
		fmt.Println("\nApplying generated policy...")
	}

	applyResult, err := applyPolicyContent(client, fileName, []byte(result.YAML), dryRun)
	if err != nil {
		return fmt.Errorf("failed to apply generated policy: %w", err)
	}

	if dryRun {
		fmt.Println("✓ Generated policy validated successfully")
	} else {
		fmt.Println("✓ Generated policy applied successfully")
	}
	fmt.Printf("  Policy: %s\n", applyResult.PolicyName)
	fmt.Printf("  MCP servers: %d created, %d updated\n", applyResult.MCPServersCreated, applyResult.MCPServersUpdated)
	fmt.Printf("  Approval workflows: %d created, %d updated\n", applyResult.PoliciesCreated, applyResult.PoliciesUpdated)
	fmt.Printf("  Tools: %d created, %d updated", applyResult.ToolsCreated, applyResult.ToolsUpdated)
	if applyResult.ToolsSkipped > 0 {
		fmt.Printf(", %d skipped", applyResult.ToolsSkipped)
	}
	fmt.Println()
	printPolicyWarnings(applyResult.Warnings)

	return nil
}

func findStarterPolicyTools(client *api.Client, serverName string) (string, []starterPolicyTool, error) {
	var tools []starterPolicyTool
	if err := client.Get(toolsListPath, &tools); err != nil {
		return "", nil, fmt.Errorf("failed to list tools: %w", err)
	}

	var exactMatches []starterPolicyTool
	for _, tool := range tools {
		if tool.Source != "mcp" {
			continue
		}
		if tool.SourceName == serverName || tool.SourceID == serverName {
			exactMatches = append(exactMatches, tool)
		}
	}
	if len(exactMatches) > 0 {
		sort.Slice(exactMatches, func(i, j int) bool { return exactMatches[i].Name < exactMatches[j].Name })
		return exactMatches[0].SourceName, exactMatches, nil
	}

	var caseInsensitiveMatches []starterPolicyTool
	for _, tool := range tools {
		if tool.Source != "mcp" {
			continue
		}
		if strings.EqualFold(tool.SourceName, serverName) || strings.EqualFold(tool.SourceID, serverName) {
			caseInsensitiveMatches = append(caseInsensitiveMatches, tool)
		}
	}
	if len(caseInsensitiveMatches) > 0 {
		sort.Slice(caseInsensitiveMatches, func(i, j int) bool { return caseInsensitiveMatches[i].Name < caseInsensitiveMatches[j].Name })
		return caseInsensitiveMatches[0].SourceName, caseInsensitiveMatches, nil
	}

	availableSet := make(map[string]struct{})
	for _, tool := range tools {
		if tool.Source == "mcp" && tool.SourceName != "" {
			availableSet[tool.SourceName] = struct{}{}
		}
	}

	available := make([]string, 0, len(availableSet))
	for name := range availableSet {
		available = append(available, name)
	}
	sort.Strings(available)

	if len(available) == 0 {
		return "", nil, fmt.Errorf("no MCP server tools found. Add a server first, then retry")
	}

	return "", nil, fmt.Errorf(
		"MCP server '%s' not found. Available servers with discovered tools: %s",
		serverName,
		strings.Join(available, ", "),
	)
}

func buildStarterPolicyPrompt(serverName string, tools []starterPolicyTool) string {
	var b strings.Builder

	fmt.Fprintf(&b, "Generate a starter Preloop policy update for MCP server %q.\n\n", serverName)
	b.WriteString("Requirements:\n")
	b.WriteString("- Preserve the current account configuration.\n")
	b.WriteString("- Scope changes to this MCP server and its tools.\n")
	b.WriteString("- Do not modify unrelated MCP servers, tool rules, approval workflows, or defaults unless needed for safe onboarding.\n")
	b.WriteString("- Reuse existing approval workflows from the current configuration when they already fit.\n")
	b.WriteString("- Prefer allow rules for clearly read-only/query/list/get/search tools.\n")
	b.WriteString("- Prefer require_approval for mutating, write-capable, privileged, destructive, or otherwise high-impact tools.\n")
	b.WriteString("- If a tool is ambiguous, prefer require_approval.\n")
	b.WriteString("- If a new approval workflow is required, keep it minimal and reusable.\n")
	b.WriteString("- Preserve any existing tool rules for this server unless they conflict with the safe starter posture.\n\n")
	b.WriteString("Discovered tools for this server:\n")

	for _, tool := range tools {
		props, required := summarizeToolSchema(tool.Schema)
		fmt.Fprintf(
			&b,
			"- %s: %s Suggested posture: %s.",
			tool.Name,
			strings.TrimSpace(tool.Description),
			starterPolicyPosture(tool),
		)
		if len(props) > 0 {
			fmt.Fprintf(&b, " Args: %s.", strings.Join(props, ", "))
		}
		if len(required) > 0 {
			fmt.Fprintf(&b, " Required args: %s.", strings.Join(required, ", "))
		}
		if len(tool.AccessRules) > 0 {
			fmt.Fprintf(&b, " Existing rules: %s.", summarizeAccessRules(tool.AccessRules))
		} else if tool.HasApprovalCondition {
			b.WriteString(" Existing approval condition present.")
		}
		b.WriteString("\n")
	}

	return b.String()
}

func starterPolicyPosture(tool starterPolicyTool) string {
	text := strings.ToLower(tool.Name + " " + tool.Description)

	switch {
	case containsAny(text, "get", "list", "read", "search", "find", "fetch", "view", "describe"):
		return "allow unless existing rules already require approval"
	case containsAny(text, "create", "update", "delete", "remove", "write", "edit", "send", "post", "merge", "deploy", "execute", "run", "restart", "shutdown", "grant", "revoke", "invite", "approve", "comment"):
		return "require approval"
	default:
		return "require approval unless the schema clearly indicates read-only behavior"
	}
}

func summarizeToolSchema(schema map[string]interface{}) ([]string, []string) {
	var props []string
	if rawProps, ok := schema["properties"].(map[string]interface{}); ok {
		for key := range rawProps {
			props = append(props, key)
		}
		sort.Strings(props)
	}

	var required []string
	if rawRequired, ok := schema["required"].([]interface{}); ok {
		for _, item := range rawRequired {
			if name, ok := item.(string); ok {
				required = append(required, name)
			}
		}
		sort.Strings(required)
	}

	return props, required
}

func summarizeAccessRules(rules []starterPolicyAccessRule) string {
	summaries := make([]string, 0, len(rules))
	for _, rule := range rules {
		summary := rule.Action
		if rule.ConditionType != "" {
			summary += " (" + rule.ConditionType + ")"
		}
		summaries = append(summaries, summary)
	}
	sort.Strings(summaries)
	return strings.Join(summaries, ", ")
}

func discoverAgents(w io.Writer, printWarnings bool) ([]AgentConfig, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return nil, fmt.Errorf("could not determine home directory: %w", err)
	}

	var discovered []AgentConfig
	for _, spec := range agentSpecs {
		for _, fullPath := range configPathsForAgentSpec(home, spec) {
			if _, err := os.Stat(fullPath); err != nil {
				continue
			}
			servers, err := spec.Parser(fullPath)
			if err != nil {
				if printWarnings {
					fmt.Fprintf(w, "  Warning: could not parse %s config at %s: %v\n", spec.Name, fullPath, err)
				}
				continue
			}
			discovered = append(discovered, AgentConfig{
				Name:       spec.Name,
				ConfigPath: fullPath,
				MCPServers: servers,
			})
			break
		}
	}
	return discovered, nil
}

func findDiscoveredAgent(discovered []AgentConfig, value string) (AgentConfig, error) {
	for _, agent := range discovered {
		if strings.EqualFold(agent.Name, value) {
			return agent, nil
		}
	}
	available := make([]string, 0, len(discovered))
	for _, agent := range discovered {
		available = append(available, agent.Name)
	}
	sort.Strings(available)
	return AgentConfig{}, fmt.Errorf("agent %q not found. Available agents: %s", value, strings.Join(available, ", "))
}

func printEnrollmentPlan(plan managedMCPEnrollmentPlan, dryRun bool) {
	mode := "Apply"
	if dryRun {
		mode = "Preview"
	}
	fmt.Printf("%s managed MCP enrollment for %s\n", mode, plan.Agent.Name)
	fmt.Printf("  Config: %s\n", plan.Agent.ConfigPath)
	fmt.Printf("  Managed server: %s -> %s\n", plan.ManagedServerName, plan.ManagedServerURL)
	discoveredNames := sortedServerNames(plan.Agent.MCPServers)
	if len(discoveredNames) > 0 {
		fmt.Printf("  Existing MCP servers: %s\n", strings.Join(discoveredNames, ", "))
	}
	fmt.Printf("  Runtime principal: %s\n", runtimePrincipalIDForAgent(plan.Agent))
	if plan.ManagedProviderName != "" && plan.ManagedModelAlias != "" {
		fmt.Printf("  Managed model: %s/%s\n", plan.ManagedProviderName, plan.ManagedModelAlias)
	}
	for _, note := range plan.Notes {
		fmt.Printf("  Note: %s\n", note)
	}
}

func buildManagedMCPEnrollmentPlan(agent AgentConfig, baseURL, token string) (managedMCPEnrollmentPlan, error) {
	if strings.EqualFold(strings.TrimSpace(agent.Name), "openclaw") {
		return buildOpenClawManagedMCPEnrollmentPlan(agent, baseURL, token)
	}

	adapter := managedMCPAdapterForAgent(agent)
	discoveredDoc, err := loadAgentConfigDocument(agent)
	if err != nil {
		return managedMCPEnrollmentPlan{}, fmt.Errorf("failed to load config document: %w", err)
	}
	managedDoc, err := deepCopyMap(discoveredDoc)
	if err != nil {
		return managedMCPEnrollmentPlan{}, err
	}
	container, err := adapter.EnsureServerContainer(managedDoc)
	if err != nil {
		return managedMCPEnrollmentPlan{}, err
	}
	container["preloop"] = adapter.BuildManagedServer(baseURL, token)

	sanitizedDiscovered, err := deepCopyMap(discoveredDoc)
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
		DiscoveredDocument:  discoveredDoc,
		ManagedDocument:     managedDoc,
		SanitizedDiscovered: sanitizedDiscovered,
		SanitizedManaged:    sanitizedManaged,
		ManagedServerName:   "preloop",
		ManagedServerURL:    strings.TrimRight(baseURL, "/") + "/mcp/v1",
	}, nil
}

func ensureDiscoveredRemoteServers(client *api.Client, agent AgentConfig) (*remoteServerSyncResult, error) {
	var existing []mcpServerResponse
	if err := client.Get("/api/v1/mcp-servers", &existing); err != nil {
		return nil, fmt.Errorf("failed to list MCP servers: %w", err)
	}
	existingByName := make(map[string]mcpServerResponse, len(existing))
	for _, item := range existing {
		existingByName[item.Name] = item
	}

	result := &remoteServerSyncResult{}
	for _, name := range sortedServerNames(agent.MCPServers) {
		server := agent.MCPServers[name]
		request, warning, importMode, ok := buildManagedRemoteServerRequest(name, server)
		if warning != "" {
			result.Warnings = append(result.Warnings, warning)
		}
		if !ok {
			result.Skipped = append(result.Skipped, name)
			continue
		}
		if _, ok := existingByName[name]; ok {
			result.Reused = append(result.Reused, name)
			continue
		}
		var created mcpServerResponse
		if err := client.Post("/api/v1/mcp-servers", request, &created); err != nil {
			return nil, fmt.Errorf("failed to add discovered MCP server %q: %w", name, err)
		}
		result.Added = append(result.Added, name)
		if importMode == "command" {
			result.ImportedFromCommand = append(result.ImportedFromCommand, name)
		}
	}
	sort.Strings(result.Added)
	sort.Strings(result.ImportedFromCommand)
	sort.Strings(result.Reused)
	sort.Strings(result.Skipped)
	sort.Strings(result.Warnings)
	return result, nil
}

func normalizeDiscoveredTransport(server MCPDef) string {
	if strings.TrimSpace(server.Transport) != "" {
		return server.Transport
	}
	return "http-streaming"
}

func authConfigForDiscoveredServer(server MCPDef) (string, map[string]interface{}) {
	if token := extractBearerToken(server); token != "" {
		return "bearer", map[string]interface{}{"token": token}
	}
	return "", nil
}

func extractBearerToken(server MCPDef) string {
	if authType, _ := server.Auth["type"].(string); strings.EqualFold(authType, "bearer") {
		if token, _ := server.Auth["token"].(string); token != "" {
			return token
		}
	}
	for key, value := range server.Headers {
		if !strings.EqualFold(key, "authorization") {
			continue
		}
		trimmed := strings.TrimSpace(value)
		if strings.HasPrefix(strings.ToLower(trimmed), "bearer ") {
			return strings.TrimSpace(trimmed[7:])
		}
	}
	for key, value := range server.Env {
		if !strings.Contains(strings.ToLower(key), "token") &&
			!strings.EqualFold(key, "authorization") {
			continue
		}
		trimmed := strings.TrimSpace(value)
		if strings.HasPrefix(strings.ToLower(trimmed), "bearer ") {
			return strings.TrimSpace(trimmed[7:])
		}
	}
	return ""
}

func getManagedAgentForDiscovered(client *api.Client, agent AgentConfig) (*managedAgentSummary, error) {
	var response managedAgentListResponse
	if err := client.Get("/api/v1/agents?limit=100", &response); err != nil {
		return nil, fmt.Errorf("failed to list managed agents: %w", err)
	}
	sourceType := runtimeSessionSourceTypeForAgent(agent.Name)
	sourceID := runtimePrincipalIDForAgent(agent)
	for _, item := range response.Items {
		if item.SessionSourceType == sourceType && item.SessionSourceID == sourceID {
			return &item, nil
		}
	}
	return nil, fmt.Errorf("managed agent not found after bootstrap for %s", agent.Name)
}

func createDurableManagedCredential(client *api.Client, agent *managedAgentSummary) (*managedAgentCredentialCreateResponse, error) {
	request := managedAgentCredentialCreateRequest{
		Name:          fmt.Sprintf("cli-managed-mcp-%s", time.Now().UTC().Format("20060102150405")),
		Description:   "Created by preloop agents enroll for managed local MCP access",
		ExpiresInDays: 365,
		Scopes:        []string{"mcp:read", "mcp:write"},
	}
	var response managedAgentCredentialCreateResponse
	if err := client.Post("/api/v1/agents/"+agent.ID+"/credentials", request, &response); err != nil {
		return nil, fmt.Errorf("failed to create durable managed-agent credential: %w", err)
	}
	return &response, nil
}

func createManagedEnrollmentRecord(client *api.Client, agentID string, request managedAgentEnrollmentCreateRequest) (*managedAgentEnrollmentSummary, error) {
	var response managedAgentEnrollmentSummary
	if err := client.Post("/api/v1/agents/"+agentID+"/enrollments", request, &response); err != nil {
		return nil, fmt.Errorf("failed to persist managed enrollment: %w", err)
	}
	return &response, nil
}

func getManagedAgentDetail(client *api.Client, agentID string) (*managedAgentDetailResponse, error) {
	var response managedAgentDetailResponse
	if err := client.Get("/api/v1/agents/"+agentID, &response); err != nil {
		return nil, fmt.Errorf("failed to fetch managed agent detail: %w", err)
	}
	return &response, nil
}

func getManagedAgentDetailForDiscovered(client *api.Client, agent AgentConfig) (*managedAgentDetailResponse, error) {
	managedAgent, err := getManagedAgentForDiscovered(client, agent)
	if err != nil {
		return nil, err
	}
	return getManagedAgentDetail(client, managedAgent.ID)
}

func validateManagedEnrollmentRecord(
	client *api.Client,
	agent AgentConfig,
	enrollmentID string,
	validationResult map[string]interface{},
	status string,
) (*managedAgentEnrollmentSummary, error) {
	managedAgent, err := getManagedAgentForDiscovered(client, agent)
	if err != nil {
		return nil, err
	}
	request := map[string]interface{}{
		"status":            status,
		"validation_result": validationResult,
	}
	var response managedAgentEnrollmentSummary
	if err := client.Post(
		"/api/v1/agents/"+managedAgent.ID+"/enrollments/"+enrollmentID+"/validate",
		request,
		&response,
	); err != nil {
		return nil, fmt.Errorf("failed to persist managed enrollment validation: %w", err)
	}
	return &response, nil
}

func restoreManagedEnrollmentRecord(
	client *api.Client,
	agent AgentConfig,
	enrollmentID string,
	backupMetadata map[string]interface{},
) (*managedAgentEnrollmentSummary, error) {
	managedAgent, err := getManagedAgentForDiscovered(client, agent)
	if err != nil {
		return nil, err
	}
	request := map[string]interface{}{
		"status": "restored",
		"backup_metadata": map[string]interface{}{
			"backup_path": backupMetadata["backup_path"],
		},
		"validation_result": map[string]interface{}{
			"restored_by": "preloop agents restore",
		},
	}
	var response managedAgentEnrollmentSummary
	if err := client.Post(
		"/api/v1/agents/"+managedAgent.ID+"/enrollments/"+enrollmentID+"/restore",
		request,
		&response,
	); err != nil {
		return nil, fmt.Errorf("failed to mark managed enrollment restored: %w", err)
	}
	return &response, nil
}

func createLocalEnrollmentBackup(agent AgentConfig, originalBytes []byte, plan managedMCPEnrollmentPlan) (*localEnrollmentState, error) {
	baseDir, err := config.GetConfigDir()
	if err != nil {
		return nil, err
	}
	runtimePrincipalID := runtimePrincipalIDForAgent(agent)
	backupDir := filepath.Join(baseDir, "agents", "backups", runtimePrincipalID)
	if err := os.MkdirAll(backupDir, 0700); err != nil {
		return nil, fmt.Errorf("failed to create backup directory: %w", err)
	}
	backupPath := filepath.Join(
		backupDir,
		fmt.Sprintf("%s-%s", time.Now().UTC().Format("20060102T150405Z"), filepath.Base(agent.ConfigPath)),
	)
	if err := os.WriteFile(backupPath, originalBytes, 0600); err != nil {
		return nil, fmt.Errorf("failed to write backup: %w", err)
	}
	return &localEnrollmentState{
		AgentName:          agent.Name,
		RuntimePrincipalID: runtimePrincipalID,
		ConfigPath:         agent.ConfigPath,
		BackupPath:         backupPath,
		ManagedServerName:  plan.ManagedServerName,
		ManagedServerURL:   plan.ManagedServerURL,
		AppliedAt:          time.Now().UTC(),
		DiscoveredConfig:   plan.SanitizedDiscovered,
		ManagedConfig:      plan.SanitizedManaged,
	}, nil
}

func saveLocalEnrollmentState(state *localEnrollmentState) error {
	statePath, err := localEnrollmentStatePath(state.RuntimePrincipalID)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(statePath), 0700); err != nil {
		return fmt.Errorf("failed to create local enrollment directory: %w", err)
	}
	data, err := json.MarshalIndent(state, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to encode local enrollment state: %w", err)
	}
	if err := os.WriteFile(statePath, data, 0600); err != nil {
		return fmt.Errorf("failed to persist local enrollment state: %w", err)
	}
	return nil
}

func loadLocalEnrollmentState(agent AgentConfig) (*localEnrollmentState, error) {
	statePath, err := localEnrollmentStatePath(runtimePrincipalIDForAgent(agent))
	if err != nil {
		return nil, err
	}
	data, err := os.ReadFile(statePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read local enrollment state: %w", err)
	}
	var state localEnrollmentState
	if err := json.Unmarshal(data, &state); err != nil {
		return nil, fmt.Errorf("failed to parse local enrollment state: %w", err)
	}
	return &state, nil
}

func localEnrollmentStatePath(runtimePrincipalID string) (string, error) {
	baseDir, err := config.GetConfigDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(baseDir, "agents", "state", runtimePrincipalID+".json"), nil
}

func loadJSONDocument(path string) (map[string]interface{}, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var doc map[string]interface{}
	if err := json.Unmarshal(data, &doc); err != nil {
		return nil, err
	}
	return doc, nil
}

func writeJSONDocument(path string, doc map[string]interface{}) error {
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to encode managed config: %w", err)
	}
	data = append(data, '\n')
	if err := os.WriteFile(path, data, 0644); err != nil {
		return fmt.Errorf("failed to write managed config: %w", err)
	}
	return nil
}

func deepCopyMap(value map[string]interface{}) (map[string]interface{}, error) {
	data, err := json.Marshal(value)
	if err != nil {
		return nil, fmt.Errorf("failed to clone config document: %w", err)
	}
	var out map[string]interface{}
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, fmt.Errorf("failed to clone config document: %w", err)
	}
	return out, nil
}

type genericManagedMCPAdapter struct {
	agent AgentConfig
}

func (a genericManagedMCPAdapter) Key() string {
	return runtimeSessionSourceTypeForAgent(a.agent.Name)
}

func (a genericManagedMCPAdapter) EnsureServerContainer(doc map[string]interface{}) (map[string]interface{}, error) {
	if servers, ok := asObjectMap(doc["mcpServers"]); ok {
		return servers, nil
	}
	if servers, ok := asObjectMap(doc["servers"]); ok {
		return servers, nil
	}
	if mcp, ok := asObjectMap(doc["mcp"]); ok {
		if servers, ok := asObjectMap(mcp["servers"]); ok {
			return servers, nil
		}
		created := make(map[string]interface{})
		mcp["servers"] = created
		return created, nil
	}

	switch strings.ToLower(strings.TrimSpace(a.agent.Name)) {
	case "claude code":
		created := make(map[string]interface{})
		doc["servers"] = created
		return created, nil
	case "codex cli":
		created := make(map[string]interface{})
		doc["mcp"] = map[string]interface{}{"servers": created}
		return created, nil
	default:
		created := make(map[string]interface{})
		doc["mcpServers"] = created
		return created, nil
	}
}

func (a genericManagedMCPAdapter) BuildManagedServer(baseURL, token string) map[string]interface{} {
	url := strings.TrimRight(baseURL, "/") + "/mcp/v1"
	switch strings.ToLower(strings.TrimSpace(a.agent.Name)) {
	case "codex cli":
		return map[string]interface{}{
			"url":       url,
			"transport": "http",
			"auth": map[string]interface{}{
				"type":  "bearer",
				"token": token,
			},
		}
	default:
		transport := "http-streaming"
		if usesNestedMCPServers(a.agent) {
			transport = "http"
		}
		entry := map[string]interface{}{
			"url": url,
			"headers": map[string]interface{}{
				"Authorization": "Bearer " + token,
			},
		}
		if transport != "" {
			entry["transport"] = transport
		}
		return entry
	}
}

func (a genericManagedMCPAdapter) ValidateManagedConfig(doc map[string]interface{}, baseURL string) map[string]interface{} {
	container := lookupMCPServerContainer(doc)
	preloop, ok := container["preloop"].(map[string]interface{})
	expectedURL := strings.TrimRight(baseURL, "/") + "/mcp/v1"
	result := map[string]interface{}{
		"adapter_key":             a.Key(),
		"preloop_server_present":  ok,
		"expected_preloop_url":    expectedURL,
		"validation_passed":       false,
		"transport_ok":            false,
		"authorization_header_ok": false,
	}
	if !ok {
		return result
	}

	result["preloop_url_ok"] = preloop["url"] == expectedURL
	result["transport_ok"] = preloop["transport"] != nil
	if headers, ok := preloop["headers"].(map[string]interface{}); ok {
		if auth, ok := headers["Authorization"].(string); ok && strings.HasPrefix(auth, "Bearer ") {
			result["authorization_header_ok"] = true
		}
	}
	result["validation_passed"] =
		result["preloop_server_present"] == true &&
			result["preloop_url_ok"] == true &&
			result["transport_ok"] == true &&
			result["authorization_header_ok"] == true
	return result
}

type openClawManagedMCPAdapter struct{}

func (a openClawManagedMCPAdapter) Key() string {
	return "openclaw"
}

func (a openClawManagedMCPAdapter) EnsureServerContainer(doc map[string]interface{}) (map[string]interface{}, error) {
	if mcp, ok := asObjectMap(doc["mcp"]); ok {
		if servers, ok := asObjectMap(mcp["servers"]); ok {
			return servers, nil
		}
		created := make(map[string]interface{})
		mcp["servers"] = created
		return created, nil
	}
	created := make(map[string]interface{})
	doc["mcp"] = map[string]interface{}{"servers": created}
	return created, nil
}

func (a openClawManagedMCPAdapter) BuildManagedServer(baseURL, token string) map[string]interface{} {
	return map[string]interface{}{
		"transport": "http",
		"url":       strings.TrimRight(baseURL, "/") + "/mcp/v1",
		"headers": map[string]interface{}{
			"Authorization": "Bearer " + token,
		},
	}
}

func (a openClawManagedMCPAdapter) ValidateManagedConfig(doc map[string]interface{}, baseURL string) map[string]interface{} {
	expectedURL := strings.TrimRight(baseURL, "/") + "/mcp/v1"
	expectedGatewayURL := strings.TrimRight(baseURL, "/") + openClawGatewayPath
	result := map[string]interface{}{
		"adapter_key":              a.Key(),
		"expected_preloop_url":     expectedURL,
		"expected_gateway_url":     expectedGatewayURL,
		"preloop_server_present":   false,
		"preloop_url_ok":           false,
		"transport_ok":             false,
		"authorization_header_ok":  false,
		"nested_mcp_servers_ok":    false,
		"only_preloop_mcp_ok":      false,
		"gateway_provider_ok":      false,
		"gateway_base_url_ok":      false,
		"gateway_api_ok":           false,
		"model_provider_rewritten": false,
		"validation_passed":        false,
	}
	mcp, ok := asObjectMap(doc["mcp"])
	if !ok {
		return result
	}
	servers, ok := asObjectMap(mcp["servers"])
	if !ok {
		return result
	}
	result["nested_mcp_servers_ok"] = true
	result["only_preloop_mcp_ok"] = len(servers) == 1
	preloop, ok := servers["preloop"].(map[string]interface{})
	if !ok {
		return result
	}
	result["preloop_server_present"] = true
	result["preloop_url_ok"] = preloop["url"] == expectedURL
	result["transport_ok"] = preloop["transport"] == "http"
	if headers, ok := preloop["headers"].(map[string]interface{}); ok {
		if auth, ok := headers["Authorization"].(string); ok && strings.HasPrefix(auth, "Bearer ") {
			result["authorization_header_ok"] = true
		}
	}
	if providers, ok := asObjectMap(lookupValue(doc, "models", "providers")); ok {
		if gatewayProvider, ok := asObjectMap(providers[openClawManagedProviderID]); ok {
			result["gateway_provider_ok"] = true
			result["gateway_base_url_ok"] = gatewayProvider["baseUrl"] == expectedGatewayURL
			if apiName, _ := gatewayProvider["api"].(string); apiName == "openai-responses" || apiName == "openai-completions" {
				result["gateway_api_ok"] = true
			}
		}
	}
	if modelRef := extractOpenClawPrimaryModel(doc); strings.HasPrefix(modelRef, openClawManagedProviderID+"/") {
		result["model_provider_rewritten"] = true
	}
	result["validation_passed"] =
		result["nested_mcp_servers_ok"] == true &&
			result["only_preloop_mcp_ok"] == true &&
			result["preloop_server_present"] == true &&
			result["preloop_url_ok"] == true &&
			result["transport_ok"] == true &&
			result["authorization_header_ok"] == true &&
			result["gateway_provider_ok"] == true &&
			result["gateway_base_url_ok"] == true &&
			result["gateway_api_ok"] == true &&
			result["model_provider_rewritten"] == true
	return result
}

func managedMCPAdapterForAgent(agent AgentConfig) managedMCPAdapter {
	switch strings.ToLower(strings.TrimSpace(agent.Name)) {
	case "openclaw":
		return openClawManagedMCPAdapter{}
	default:
		return genericManagedMCPAdapter{agent: agent}
	}
}

func usesNestedMCPServers(agent AgentConfig) bool {
	switch strings.ToLower(strings.TrimSpace(agent.Name)) {
	case "openclaw", "codex cli":
		return true
	default:
		return false
	}
}

func lookupMCPServerContainer(doc map[string]interface{}) map[string]interface{} {
	if servers, ok := asObjectMap(doc["mcpServers"]); ok {
		return servers
	}
	if servers, ok := asObjectMap(doc["servers"]); ok {
		return servers
	}
	if mcp, ok := asObjectMap(doc["mcp"]); ok {
		if servers, ok := asObjectMap(mcp["servers"]); ok {
			return servers
		}
	}
	return map[string]interface{}{}
}

func clientBaseURLForFlags() string {
	cfg, err := config.Resolve(FlagToken, FlagURL)
	if err == nil && cfg.APIURL != "" {
		return cfg.APIURL
	}
	return api.DefaultBaseURL
}

func asObjectMap(value interface{}) (map[string]interface{}, bool) {
	if value == nil {
		return nil, false
	}
	obj, ok := value.(map[string]interface{})
	return obj, ok
}

func sanitizeConfigSnapshot(value interface{}) {
	switch typed := value.(type) {
	case map[string]interface{}:
		for key, child := range typed {
			if isSensitiveKey(key) {
				typed[key] = "<redacted>"
				continue
			}
			sanitizeConfigSnapshot(child)
		}
	case []interface{}:
		for _, child := range typed {
			sanitizeConfigSnapshot(child)
		}
	}
}

func isSensitiveKey(key string) bool {
	switch strings.ToLower(strings.TrimSpace(key)) {
	case "authorization", "token", "api_key", "apikey", "password", "secret":
		return true
	default:
		return false
	}
}

func defaultStarterPolicyFileName(serverName string) string {
	safe := strings.ToLower(serverName)
	replacer := strings.NewReplacer(" ", "-", "/", "-", "\\", "-", ":", "-", ".", "-")
	safe = replacer.Replace(safe)
	safe = strings.Trim(safe, "-")
	if safe == "" {
		safe = "mcp-server"
	}
	return fmt.Sprintf("%s-starter-policy.yaml", safe)
}

func containsAny(value string, parts ...string) bool {
	for _, part := range parts {
		if strings.Contains(value, part) {
			return true
		}
	}
	return false
}

// ── Config parsers ───────────────────────────────────────────────────

// parseClaudeConfig reads Claude Desktop / Code config format.
func parseClaudeConfig(path string) (map[string]MCPDef, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return parseServerMapFromJSON(data)
}

// parseGenericMCP reads configs with a top-level "mcpServers" key.
func parseGenericMCP(path string) (map[string]MCPDef, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return parseServerMapFromJSON(data)
}

// parseGeminiConfig reads Gemini CLI's settings.json format.
func parseGeminiConfig(path string) (map[string]MCPDef, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	return parseServerMapFromJSON(data)
}

func parseServerMapFromJSON(data []byte) (map[string]MCPDef, error) {
	var root map[string]json.RawMessage
	if err := json.Unmarshal(data, &root); err != nil {
		return nil, err
	}
	var doc map[string]interface{}
	if err := json.Unmarshal(data, &doc); err != nil {
		return nil, err
	}
	return parseServerMapFromDocument(doc), nil
}
