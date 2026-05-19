package cmd

import (
	"encoding/base64"
	"io"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const hermesSampleConfig = `# Sample Hermes Agent config
mcp_servers:
  github:
    command: "npx"
    args:
      - "-y"
      - "@modelcontextprotocol/server-github"
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "ghp_existing"
  remote_api:
    url: "https://mcp.example.com/mcp"
    headers:
      Authorization: "Bearer existing-token"
`

func TestParseHermesConfig_StdioAndHTTPServers(t *testing.T) {
	dir := t.TempDir()
	configPath := filepath.Join(dir, "config.yaml")
	if err := os.WriteFile(configPath, []byte(hermesSampleConfig), 0644); err != nil {
		t.Fatalf("failed to write Hermes config: %v", err)
	}

	servers, err := parseHermesConfig(configPath)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	github, ok := servers["github"]
	if !ok {
		t.Fatalf("expected github stdio server, got %+v", servers)
	}
	if github.Command != "npx" {
		t.Fatalf("unexpected github command: %q", github.Command)
	}
	if len(github.Args) != 2 || github.Args[0] != "-y" {
		t.Fatalf("unexpected github args: %+v", github.Args)
	}
	if github.Env["GITHUB_PERSONAL_ACCESS_TOKEN"] != "ghp_existing" {
		t.Fatalf("unexpected github env: %+v", github.Env)
	}

	remote, ok := servers["remote_api"]
	if !ok {
		t.Fatalf("expected remote_api HTTP server, got %+v", servers)
	}
	if remote.URL != "https://mcp.example.com/mcp" {
		t.Fatalf("unexpected remote_api URL: %q", remote.URL)
	}
	if remote.Headers["Authorization"] != "Bearer existing-token" {
		t.Fatalf("unexpected remote_api headers: %+v", remote.Headers)
	}
}

func TestParseHermesConfig_EmptyOrMissingDocument(t *testing.T) {
	dir := t.TempDir()

	emptyPath := filepath.Join(dir, "empty.yaml")
	if err := os.WriteFile(emptyPath, []byte(""), 0644); err != nil {
		t.Fatalf("failed to write empty Hermes config: %v", err)
	}
	servers, err := parseHermesConfig(emptyPath)
	if err != nil {
		t.Fatalf("unexpected error parsing empty config: %v", err)
	}
	if len(servers) != 0 {
		t.Fatalf("expected no servers from empty config, got %+v", servers)
	}

	commentsOnly := filepath.Join(dir, "comments.yaml")
	if err := os.WriteFile(commentsOnly, []byte("# only comments\n"), 0644); err != nil {
		t.Fatalf("failed to write commented Hermes config: %v", err)
	}
	servers, err = parseHermesConfig(commentsOnly)
	if err != nil {
		t.Fatalf("unexpected error parsing comments-only config: %v", err)
	}
	if len(servers) != 0 {
		t.Fatalf("expected no servers from comments-only config, got %+v", servers)
	}
}

func TestRuntimeSessionSourceTypeForHermesAgent(t *testing.T) {
	if got := runtimeSessionSourceTypeForAgent("Hermes"); got != hermesSourceType {
		t.Fatalf("expected source type %q, got %q", hermesSourceType, got)
	}
	if got := runtimeSessionSourceTypeForAgent("hermes"); got != hermesSourceType {
		t.Fatalf("expected source type %q, got %q", hermesSourceType, got)
	}
}

func TestDiscoverAgentsFindsHermesYAMLConfig(t *testing.T) {
	home := t.TempDir()
	oldHome := os.Getenv("HOME")
	if err := os.Setenv("HOME", home); err != nil {
		t.Fatalf("failed to set HOME: %v", err)
	}
	defer func() {
		_ = os.Setenv("HOME", oldHome)
	}()

	configPath := filepath.Join(home, ".hermes", "config.yaml")
	if err := os.MkdirAll(filepath.Dir(configPath), 0755); err != nil {
		t.Fatalf("failed to create hermes dir: %v", err)
	}
	if err := os.WriteFile(configPath, []byte(hermesSampleConfig), 0644); err != nil {
		t.Fatalf("failed to write hermes config: %v", err)
	}

	discovered, err := discoverAgents(io.Discard, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	for _, agent := range discovered {
		if agent.Name != hermesAgentName {
			continue
		}
		if agent.ConfigPath != configPath {
			t.Fatalf("expected hermes config path %q, got %q", configPath, agent.ConfigPath)
		}
		if _, ok := agent.MCPServers["github"]; !ok {
			t.Fatalf("expected discovered hermes mcp servers to include github, got %+v", agent.MCPServers)
		}
		return
	}
	t.Fatalf("expected Hermes to be discovered, got %#v", discovered)
}

func TestDiscoverAgentsFindsInstalledHermesWithoutConfig(t *testing.T) {
	home := t.TempDir()
	oldHome := os.Getenv("HOME")
	if err := os.Setenv("HOME", home); err != nil {
		t.Fatalf("failed to set HOME: %v", err)
	}
	defer func() {
		_ = os.Setenv("HOME", oldHome)
	}()

	if err := os.MkdirAll(filepath.Join(home, ".hermes", "sessions"), 0755); err != nil {
		t.Fatalf("failed to create hermes install marker: %v", err)
	}

	discovered, err := discoverAgents(io.Discard, false)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	for _, agent := range discovered {
		if agent.Name != hermesAgentName {
			continue
		}
		wantPath := filepath.Join(home, hermesBootstrapConfigPath)
		if agent.ConfigPath != wantPath {
			t.Fatalf("expected synthesized Hermes config path %q, got %q", wantPath, agent.ConfigPath)
		}
		if len(agent.MCPServers) != 0 {
			t.Fatalf("expected empty MCP server set for unconfigured Hermes, got %+v", agent.MCPServers)
		}
		return
	}
	t.Fatalf("expected Hermes to be discovered from install markers, got %#v", discovered)
}

func TestBuildManagedMCPEnrollmentPlan_HermesAddsPreloopServer(t *testing.T) {
	dir := t.TempDir()
	configPath := filepath.Join(dir, "config.yaml")
	if err := os.WriteFile(configPath, []byte(hermesSampleConfig), 0644); err != nil {
		t.Fatalf("failed to write hermes config: %v", err)
	}

	plan, err := buildManagedMCPEnrollmentPlan(AgentConfig{
		Name:       hermesAgentName,
		ConfigPath: configPath,
	}, "https://preloop.example", "hermes-durable-token")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	servers, ok := plan.ManagedDocument["mcp_servers"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected mcp_servers map in managed Hermes config, got %#v", plan.ManagedDocument)
	}
	if _, ok := servers["github"]; !ok {
		t.Fatalf("expected existing github server to be preserved, got %#v", servers)
	}
	preloop, ok := servers["preloop"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected preloop server entry, got %#v", servers)
	}
	if preloop["url"] != "https://preloop.example/mcp/v1" {
		t.Fatalf("unexpected Preloop URL: %#v", preloop)
	}
	headers, ok := preloop["headers"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected headers in preloop server, got %#v", preloop)
	}
	if headers["Authorization"] != "Bearer hermes-durable-token" {
		t.Fatalf("unexpected Authorization header: %+v", headers)
	}
	if enabled, _ := preloop["enabled"].(bool); !enabled {
		t.Fatalf("expected preloop server to be enabled, got %#v", preloop)
	}

	sanitizedServers, ok := plan.SanitizedManaged["mcp_servers"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected sanitized mcp_servers map, got %#v", plan.SanitizedManaged)
	}
	sanitizedPreloop := sanitizedServers["preloop"].(map[string]interface{})
	sanitizedHeaders := sanitizedPreloop["headers"].(map[string]interface{})
	if sanitizedHeaders["Authorization"] != "<redacted>" {
		t.Fatalf("expected sanitized auth header, got %+v", sanitizedHeaders)
	}

	sanitizedExisting := sanitizedServers["remote_api"].(map[string]interface{})
	existingHeaders := sanitizedExisting["headers"].(map[string]interface{})
	if existingHeaders["Authorization"] != "<redacted>" {
		t.Fatalf("expected upstream Authorization header to be redacted, got %+v", existingHeaders)
	}
}

func TestBuildManagedMCPEnrollmentPlan_HermesAllowsMissingConfig(t *testing.T) {
	dir := t.TempDir()
	configPath := filepath.Join(dir, ".hermes", "config.yaml")

	plan, err := buildManagedMCPEnrollmentPlan(AgentConfig{
		Name:       hermesAgentName,
		ConfigPath: configPath,
	}, "https://preloop.example", "hermes-durable-token")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	servers := plan.ManagedDocument["mcp_servers"].(map[string]interface{})
	preloop := servers["preloop"].(map[string]interface{})
	if preloop["url"] != "https://preloop.example/mcp/v1" {
		t.Fatalf("unexpected Preloop URL: %#v", preloop)
	}
	headers := preloop["headers"].(map[string]interface{})
	if headers["Authorization"] != "Bearer hermes-durable-token" {
		t.Fatalf("unexpected Authorization header: %+v", headers)
	}
}

func TestWriteHermesAgentConfigDocument_RoundTripsThroughYAML(t *testing.T) {
	dir := t.TempDir()
	configPath := filepath.Join(dir, "nested", "config.yaml")

	doc := map[string]interface{}{
		"mcp_servers": map[string]interface{}{
			"preloop": map[string]interface{}{
				"url": "https://preloop.example/mcp/v1",
				"headers": map[string]interface{}{
					"Authorization": "Bearer round-trip-token",
				},
			},
		},
	}

	if err := writeHermesAgentConfigDocument(configPath, doc); err != nil {
		t.Fatalf("failed to write hermes config: %v", err)
	}

	written, err := os.ReadFile(configPath)
	if err != nil {
		t.Fatalf("failed to read back hermes config: %v", err)
	}
	if !strings.Contains(string(written), "mcp_servers:") {
		t.Fatalf("expected mcp_servers key in written YAML, got %q", string(written))
	}

	reloaded, err := loadHermesAgentConfigDocument(configPath)
	if err != nil {
		t.Fatalf("failed to reload hermes config: %v", err)
	}
	servers, ok := reloaded["mcp_servers"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected mcp_servers to round-trip, got %#v", reloaded)
	}
	preloop, ok := servers["preloop"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected preloop server to round-trip, got %#v", servers)
	}
	if preloop["url"] != "https://preloop.example/mcp/v1" {
		t.Fatalf("unexpected reloaded URL: %#v", preloop)
	}
}

func TestHermesAdapterValidateManagedConfig_Passes(t *testing.T) {
	adapter := managedMCPAdapterForAgent(AgentConfig{Name: hermesAgentName})
	doc := map[string]interface{}{
		"mcp_servers": map[string]interface{}{
			"preloop": adapter.BuildManagedServer("https://preloop.example", "hermes-token"),
		},
	}
	result := adapter.ValidateManagedConfig(doc, "https://preloop.example")
	if passed, _ := result["validation_passed"].(bool); !passed {
		t.Fatalf("expected hermes adapter validation to pass, got %#v", result)
	}
	if result["adapter_key"] != hermesSourceType {
		t.Fatalf("expected adapter key %q, got %q", hermesSourceType, result["adapter_key"])
	}
}

func TestHermesAdapterValidateManagedConfig_FailsWithoutPreloopEntry(t *testing.T) {
	adapter := managedMCPAdapterForAgent(AgentConfig{Name: hermesAgentName})
	doc := map[string]interface{}{
		"mcp_servers": map[string]interface{}{
			"github": map[string]interface{}{
				"url": "https://example.com/mcp",
			},
		},
	}
	result := adapter.ValidateManagedConfig(doc, "https://preloop.example")
	if passed, _ := result["validation_passed"].(bool); passed {
		t.Fatalf("expected validation to fail without Preloop entry, got %#v", result)
	}
}

func TestSupportsManagedGateway_IncludesHermes(t *testing.T) {
	if !supportsManagedGateway(AgentConfig{Name: hermesAgentName}) {
		t.Fatalf("expected Hermes to support the managed gateway")
	}
	if !supportsManagedGateway(AgentConfig{Name: "hermes"}) {
		t.Fatalf("expected lowercase hermes to support the managed gateway")
	}
}

func TestApplyHermesManagedGateway_RewritesModelBlock(t *testing.T) {
	plan := managedMCPEnrollmentPlan{
		ManagedDocument: map[string]interface{}{
			"model": map[string]interface{}{
				"default":  "gpt-5.4",
				"provider": "openai-codex",
				"base_url": "https://chatgpt.com/backend-api/codex",
			},
			"mcp_servers": map[string]interface{}{
				"preloop": map[string]interface{}{
					"url": "https://preloop.example/mcp/v1",
					"headers": map[string]interface{}{
						"Authorization": "Bearer hermes-durable-token",
					},
				},
			},
		},
	}

	plan, err := applyHermesManagedGateway(
		plan,
		"https://preloop.example",
		"hermes-durable-token",
		"openai/gpt-5.4",
	)
	if err != nil {
		t.Fatalf("unexpected gateway apply error: %v", err)
	}

	model, ok := plan.ManagedDocument["model"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected model mapping in managed doc, got %#v", plan.ManagedDocument["model"])
	}
	if model["provider"] != hermesGatewayProviderName {
		t.Fatalf("expected provider %q, got %#v", hermesGatewayProviderName, model["provider"])
	}
	if model["base_url"] != "https://preloop.example/openai/v1" {
		t.Fatalf("unexpected hermes gateway base_url: %#v", model["base_url"])
	}
	if model["api_key"] != "hermes-durable-token" {
		t.Fatalf("unexpected hermes gateway api_key: %#v", model["api_key"])
	}
	if model["default"] != "openai/gpt-5.4" {
		t.Fatalf("unexpected hermes gateway model default: %#v", model["default"])
	}
	if _, exists := model["model"]; exists {
		t.Fatalf("expected stale `model` shorthand to be cleared")
	}
	if plan.ManagedModelAlias != "openai/gpt-5.4" {
		t.Fatalf("unexpected ManagedModelAlias: %q", plan.ManagedModelAlias)
	}
	if plan.ManagedProviderName != "preloop" {
		t.Fatalf("unexpected ManagedProviderName: %q", plan.ManagedProviderName)
	}

	servers := plan.ManagedDocument["mcp_servers"].(map[string]interface{})
	preloop := servers["preloop"].(map[string]interface{})
	if preloop["url"] != "https://preloop.example/mcp/v1" {
		t.Fatalf("expected pre-existing MCP entry to be preserved, got %#v", preloop)
	}
}

func TestParseHermesManagedGatewayUpstreamResolvesProviderSpecificEnvKey(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("DEEPSEEK_API_KEY", "")
	configPath := filepath.Join(home, ".hermes", "config.yaml")
	if err := os.MkdirAll(filepath.Dir(configPath), 0o755); err != nil {
		t.Fatalf("failed to create Hermes config dir: %v", err)
	}
	if err := os.WriteFile(
		configPath,
		[]byte(`model:
  default: deepseek-v4-pro
  provider: deepseek
  base_url: https://api.deepseek.com/v1
`),
		0o600,
	); err != nil {
		t.Fatalf("failed to write Hermes config: %v", err)
	}
	if err := os.WriteFile(
		filepath.Join(home, hermesEnvFile),
		[]byte("DEEPSEEK_API_KEY=deepseek-secret\n"),
		0o600,
	); err != nil {
		t.Fatalf("failed to write Hermes env file: %v", err)
	}

	upstream, err := parseHermesManagedGatewayUpstream(AgentConfig{
		Name:       hermesAgentName,
		ConfigPath: configPath,
	})
	if err != nil {
		t.Fatalf("unexpected Hermes upstream parse error: %v", err)
	}
	if upstream == nil {
		t.Fatal("expected Hermes upstream to be resolved")
	}
	if !upstream.CanRouteThroughGateway() {
		t.Fatalf("expected deepseek upstream to be gateway-routable, got %#v", upstream)
	}
	if upstream.ProviderName != "deepseek" {
		t.Fatalf("expected provider deepseek, got %q", upstream.ProviderName)
	}
	if upstream.ModelIdentifier != "deepseek-v4-pro" {
		t.Fatalf("expected model id deepseek-v4-pro, got %q", upstream.ModelIdentifier)
	}
	if upstream.APIKey != "deepseek-secret" {
		t.Fatalf("expected provider-specific env key to resolve, got %q", upstream.APIKey)
	}
	if upstream.ManagedModelAlias != "deepseek/deepseek-v4-pro" {
		t.Fatalf("unexpected managed model alias %q", upstream.ManagedModelAlias)
	}
}

func TestApplyHermesManagedGateway_CreatesModelBlockWhenMissing(t *testing.T) {
	plan := managedMCPEnrollmentPlan{
		ManagedDocument: map[string]interface{}{},
	}

	plan, err := applyHermesManagedGateway(
		plan,
		"https://preloop.example/",
		"hermes-token",
		"openai/gpt-5.4",
	)
	if err != nil {
		t.Fatalf("unexpected gateway apply error: %v", err)
	}

	model, ok := plan.ManagedDocument["model"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected applyHermesManagedGateway to materialise the model block, got %#v", plan.ManagedDocument)
	}
	if model["base_url"] != "https://preloop.example/openai/v1" {
		t.Fatalf("expected trailing slash to be stripped from base URL, got %#v", model["base_url"])
	}
}

func TestHermesAdapterValidateManagedConfig_PassesWithGatewayConfigured(t *testing.T) {
	adapter := managedMCPAdapterForAgent(AgentConfig{Name: hermesAgentName})
	doc := map[string]interface{}{
		"mcp_servers": map[string]interface{}{
			"preloop": adapter.BuildManagedServer("https://preloop.example", "hermes-token"),
		},
		"model": map[string]interface{}{
			"provider": hermesGatewayProviderName,
			"base_url": "https://preloop.example/openai/v1",
			"api_key":  "hermes-token",
			"default":  "openai/gpt-5.4",
		},
	}
	result := adapter.ValidateManagedConfig(doc, "https://preloop.example")
	if passed, _ := result["validation_passed"].(bool); !passed {
		t.Fatalf("expected gateway-configured validation to pass, got %#v", result)
	}
	if result["gateway_provider_ok"] != true {
		t.Fatalf("expected gateway_provider_ok=true, got %#v", result)
	}
	if result["gateway_base_url_ok"] != true {
		t.Fatalf("expected gateway_base_url_ok=true, got %#v", result)
	}
	if result["gateway_model_alias"] != "openai/gpt-5.4" {
		t.Fatalf("unexpected gateway alias surfaced by validation: %#v", result["gateway_model_alias"])
	}
}

func TestHermesAdapterValidateManagedConfig_FailsWhenGatewayBaseURLWrong(t *testing.T) {
	adapter := managedMCPAdapterForAgent(AgentConfig{Name: hermesAgentName})
	doc := map[string]interface{}{
		"mcp_servers": map[string]interface{}{
			"preloop": adapter.BuildManagedServer("https://preloop.example", "hermes-token"),
		},
		"model": map[string]interface{}{
			"provider": hermesGatewayProviderName,
			"base_url": "https://chatgpt.com/backend-api/codex",
			"default":  "openai/gpt-5.4",
		},
	}
	result := adapter.ValidateManagedConfig(doc, "https://preloop.example")
	if passed, _ := result["validation_passed"].(bool); passed {
		t.Fatalf("expected validation to fail when gateway base_url is wrong, got %#v", result)
	}
}

func TestExtractHermesModelSelection_StringShorthand(t *testing.T) {
	modelRef, providerHint, baseURL := extractHermesModelSelection(map[string]interface{}{
		"model": "anthropic/claude-opus-4.6",
	})
	if modelRef != "anthropic/claude-opus-4.6" || providerHint != "" || baseURL != "" {
		t.Fatalf("unexpected shorthand parse: model=%q hint=%q baseURL=%q", modelRef, providerHint, baseURL)
	}
}

func TestExtractHermesModelSelection_StructuredMapping(t *testing.T) {
	modelRef, providerHint, baseURL := extractHermesModelSelection(map[string]interface{}{
		"model": map[string]interface{}{
			"default":  "gpt-5.4",
			"provider": "openai-codex",
			"base_url": "https://chatgpt.com/backend-api/codex",
		},
	})
	if modelRef != "gpt-5.4" || providerHint != "openai-codex" ||
		baseURL != "https://chatgpt.com/backend-api/codex" {
		t.Fatalf("unexpected structured parse: model=%q hint=%q baseURL=%q", modelRef, providerHint, baseURL)
	}
}

func TestSplitHermesModelRef_PrefersExplicitProviderHint(t *testing.T) {
	provider, model := splitHermesModelRef("anthropic/claude-opus-4.6", "openrouter")
	if provider != "openrouter" || model != "claude-opus-4.6" {
		t.Fatalf("expected explicit provider hint to win, got provider=%q model=%q", provider, model)
	}
}

func TestSplitHermesModelRef_DefaultsToOpenRouterWhenAuto(t *testing.T) {
	provider, model := splitHermesModelRef("hermes-3-llama-3.1-405b", "auto")
	if provider != "openrouter" || model != "hermes-3-llama-3.1-405b" {
		t.Fatalf("expected auto to default to openrouter, got provider=%q model=%q", provider, model)
	}
}

func TestNormalizeHermesManagedAlias_CollapsesCodexProvider(t *testing.T) {
	if got := normalizeHermesManagedAlias("gpt-5.4", "openai-codex", "gpt-5.4"); got != "openai/gpt-5.4" {
		t.Fatalf("expected openai/gpt-5.4, got %q", got)
	}
	if got := normalizeHermesManagedAlias("anthropic/claude-opus-4.6", "anthropic", "claude-opus-4.6"); got != "anthropic/claude-opus-4.6" {
		t.Fatalf("expected pre-existing slashed alias to round-trip, got %q", got)
	}
}

func TestParseHermesManagedGatewayUpstream_ImportsCodexOAuth(t *testing.T) {
	home := t.TempDir()
	oldHome := os.Getenv("HOME")
	if err := os.Setenv("HOME", home); err != nil {
		t.Fatalf("failed to override HOME: %v", err)
	}
	defer func() { _ = os.Setenv("HOME", oldHome) }()

	configPath := filepath.Join(home, hermesBootstrapConfigPath)
	if err := os.MkdirAll(filepath.Dir(configPath), 0755); err != nil {
		t.Fatalf("failed to create hermes dir: %v", err)
	}
	configBody := `model:
  default: gpt-5.4
  provider: openai-codex
  base_url: https://chatgpt.com/backend-api/codex
`
	if err := os.WriteFile(configPath, []byte(configBody), 0644); err != nil {
		t.Fatalf("failed to seed hermes config: %v", err)
	}

	jwtPayload := base64.RawURLEncoding.EncodeToString([]byte(`{"exp":1893456000,"https://api.openai.com/auth":{"chatgpt_account_id":"acct-test"}}`))
	accessToken := "header." + jwtPayload + ".sig"
	authJSON := `{
        "version": 1,
        "providers": {
            "openai-codex": {
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": "` + accessToken + `",
                    "refresh_token": "refresh-token"
                }
            }
        },
        "active_provider": "openai-codex"
    }`
	authPath := filepath.Join(home, hermesAuthFile)
	if err := os.WriteFile(authPath, []byte(authJSON), 0600); err != nil {
		t.Fatalf("failed to seed hermes auth.json: %v", err)
	}

	upstream, err := parseHermesManagedGatewayUpstream(AgentConfig{
		Name:       hermesAgentName,
		ConfigPath: configPath,
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if upstream == nil {
		t.Fatal("expected hermes upstream to resolve")
	}
	if upstream.CredentialType != "oauth_openai_codex" {
		t.Fatalf("expected oauth_openai_codex credentials, got %#v", upstream.CredentialType)
	}
	if upstream.ProviderName != "openai-codex" {
		t.Fatalf("expected openai-codex provider name, got %q", upstream.ProviderName)
	}
	if upstream.ManagedModelAlias != "openai/gpt-5.4" {
		t.Fatalf("expected gateway alias openai/gpt-5.4, got %q", upstream.ManagedModelAlias)
	}
	if upstream.ModelIdentifier != "gpt-5.4" {
		t.Fatalf("expected model identifier gpt-5.4, got %q", upstream.ModelIdentifier)
	}
	if upstream.APIEndpoint != "https://chatgpt.com/backend-api/codex" {
		t.Fatalf("unexpected API endpoint: %q", upstream.APIEndpoint)
	}
	if got := upstream.CredentialPayload["access"]; got != accessToken {
		t.Fatalf("expected access token in payload, got %#v", got)
	}
	if got := upstream.CredentialPayload["account_id"]; got != "acct-test" {
		t.Fatalf("expected account_id from JWT, got %#v", got)
	}
	if !upstream.CanRouteThroughGateway() {
		t.Fatalf("expected upstream to be routable, got %#v", upstream)
	}
}

func TestParseHermesManagedGatewayUpstream_ResolvesOpenAIKeyFromEnvFile(t *testing.T) {
	home := t.TempDir()
	oldHome := os.Getenv("HOME")
	if err := os.Setenv("HOME", home); err != nil {
		t.Fatalf("failed to override HOME: %v", err)
	}
	defer func() { _ = os.Setenv("HOME", oldHome) }()

	for _, key := range []string{"OPENAI_API_KEY", "OPENROUTER_API_KEY"} {
		old, present := os.LookupEnv(key)
		_ = os.Unsetenv(key)
		defer func(k, v string, p bool) {
			if p {
				_ = os.Setenv(k, v)
			} else {
				_ = os.Unsetenv(k)
			}
		}(key, old, present)
	}

	configPath := filepath.Join(home, hermesBootstrapConfigPath)
	if err := os.MkdirAll(filepath.Dir(configPath), 0755); err != nil {
		t.Fatalf("failed to create hermes dir: %v", err)
	}
	configBody := `model:
  default: gpt-5.4
  provider: openai
`
	if err := os.WriteFile(configPath, []byte(configBody), 0644); err != nil {
		t.Fatalf("failed to seed hermes config: %v", err)
	}

	envPath := filepath.Join(home, hermesEnvFile)
	if err := os.MkdirAll(filepath.Dir(envPath), 0755); err != nil {
		t.Fatalf("failed to create hermes dir: %v", err)
	}
	if err := os.WriteFile(envPath, []byte("OPENAI_API_KEY=sk-test-1234\n"), 0600); err != nil {
		t.Fatalf("failed to seed hermes .env: %v", err)
	}

	upstream, err := parseHermesManagedGatewayUpstream(AgentConfig{
		Name:       hermesAgentName,
		ConfigPath: configPath,
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if upstream == nil {
		t.Fatal("expected upstream resolution from .env API key")
	}
	if upstream.APIKey != "sk-test-1234" {
		t.Fatalf("expected API key from .env, got %q", upstream.APIKey)
	}
	if upstream.ManagedModelAlias != "openai/gpt-5.4" {
		t.Fatalf("expected openai/gpt-5.4 alias, got %q", upstream.ManagedModelAlias)
	}
	if !upstream.CanRouteThroughGateway() {
		t.Fatalf("expected upstream to route through gateway, got %#v", upstream)
	}
}

func TestParseHermesManagedGatewayUpstream_SkipsAlreadyManagedConfig(t *testing.T) {
	home := t.TempDir()
	oldHome := os.Getenv("HOME")
	if err := os.Setenv("HOME", home); err != nil {
		t.Fatalf("failed to override HOME: %v", err)
	}
	defer func() { _ = os.Setenv("HOME", oldHome) }()

	configPath := filepath.Join(home, hermesBootstrapConfigPath)
	if err := os.MkdirAll(filepath.Dir(configPath), 0755); err != nil {
		t.Fatalf("failed to create hermes dir: %v", err)
	}
	body := `model:
  default: preloop/openai/gpt-5.4
  provider: custom
  base_url: https://preloop.example/openai/v1
`
	if err := os.WriteFile(configPath, []byte(body), 0644); err != nil {
		t.Fatalf("failed to seed hermes config: %v", err)
	}

	upstream, err := parseHermesManagedGatewayUpstream(AgentConfig{
		Name:       hermesAgentName,
		ConfigPath: configPath,
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if upstream != nil {
		t.Fatalf("expected nil upstream when already pointed at preloop, got %#v", upstream)
	}
}

func TestManagedGatewayBindingConfigKey_Hermes(t *testing.T) {
	got := managedGatewayBindingConfigKey(AgentConfig{Name: hermesAgentName})
	if got != "model.default" {
		t.Fatalf("expected model.default, got %q", got)
	}
}
