package cmd

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/preloop/preloop/cli/internal/api"
)

func TestOpenClawConfigPathsIncludesCurrentLocations(t *testing.T) {
	home := "/tmp/preloop-home"
	t.Setenv("OPENCLAW_CONFIG_PATH", "~/custom/openclaw.json5")
	t.Setenv("OPENCLAW_HOME", "~/state/openclaw")
	t.Setenv("OPENCLAW_STATE_DIR", "")
	t.Setenv("OPENCLAW_CONFIG_DIR", "~/xdg/openclaw")

	paths := openClawConfigPaths(home)
	joined := strings.Join(paths, "\n")

	for _, want := range []string{
		filepath.Join(home, "custom", "openclaw.json5"),
		filepath.Join(home, ".openclaw", "openclaw.json"),
		filepath.Join(home, ".openclaw", "openclaw.json5"),
		filepath.Join(home, ".openclaw", "config.json"),
		filepath.Join(home, ".openclaw", "config.json5"),
		filepath.Join(home, ".config", "openclaw", "openclaw.json"),
		filepath.Join(home, ".config", "openclaw", "config.json5"),
		filepath.Join(home, "state", "openclaw", "config.json5"),
		filepath.Join(home, "xdg", "openclaw", "openclaw.json"),
	} {
		if !strings.Contains(joined, want) {
			t.Fatalf("expected %q in OpenClaw config candidates:\n%s", want, joined)
		}
	}
}

func TestParseOpenClawConfigJSON5(t *testing.T) {
	tempDir := t.TempDir()
	configPath := filepath.Join(tempDir, "openclaw.json5")
	t.Setenv("OPENAI_API_KEY", "provider-secret")

	config := `{
  // OpenClaw accepts JSON5 with comments and trailing commas.
  agents: {
    defaults: {
      model: {
        primary: "openai/gpt-5",
        fallbacks: ["openai/gpt-4.1"],
      },
    },
  },
  models: {
    providers: {
      openai: {
        baseUrl: "https://api.openai.com/v1",
        api: "openai-responses",
        apiKey: "${OPENAI_API_KEY}",
        models: [
          {
            id: "gpt-5",
            name: "GPT-5",
            contextWindow: 128000,
          },
        ],
      },
    },
  },
  mcp: {
    servers: {
      preexisting: {
        transport: "http",
        url: "https://mcp.example.com/v1",
      },
    },
  },
}`
	if err := os.WriteFile(configPath, []byte(config), 0o600); err != nil {
		t.Fatalf("failed to write test config: %v", err)
	}

	parsed, err := parseOpenClawConfig(configPath)
	if err != nil {
		t.Fatalf("parseOpenClawConfig returned error: %v", err)
	}

	if parsed.ModelRef != "openai/gpt-5" {
		t.Fatalf("expected model ref openai/gpt-5, got %q", parsed.ModelRef)
	}
	if parsed.ModelAlias != "openai/gpt-5" {
		t.Fatalf("expected model alias openai/gpt-5, got %q", parsed.ModelAlias)
	}
	if parsed.ProviderName != "openai" {
		t.Fatalf("expected provider name openai, got %q", parsed.ProviderName)
	}
	if parsed.ProviderAPI != "openai-responses" {
		t.Fatalf("expected provider API openai-responses, got %q", parsed.ProviderAPI)
	}
	if parsed.ProviderBaseURL != "https://api.openai.com/v1" {
		t.Fatalf("expected provider base URL to be preserved, got %q", parsed.ProviderBaseURL)
	}
	if parsed.ProviderAPIKey != "provider-secret" {
		t.Fatalf("expected resolved provider API key, got %q", parsed.ProviderAPIKey)
	}
	if len(parsed.MCPServers) != 1 {
		t.Fatalf("expected one MCP server, got %d", len(parsed.MCPServers))
	}
	if parsed.MCPServers["preexisting"].URL != "https://mcp.example.com/v1" {
		t.Fatalf("expected MCP server URL to parse, got %+v", parsed.MCPServers["preexisting"])
	}
	if got := parsed.ModelCatalog["name"]; got != "GPT-5" {
		t.Fatalf("expected model catalog to be preserved, got %#v", parsed.ModelCatalog)
	}
}

func TestBuildOpenClawManagedMCPEnrollmentPlanRewritesGateway(t *testing.T) {
	tempDir := t.TempDir()
	configPath := filepath.Join(tempDir, "openclaw.json")
	t.Setenv("OPENAI_API_KEY", "provider-secret")

	config := `{
  agents: {
    defaults: {
      model: {
        primary: "openai/gpt-5",
        fallbacks: ["openai/gpt-4.1"],
      },
      models: {
        "openai/gpt-5": { alias: "GPT 5" },
      },
    },
    list: [
      {
        id: "main",
        model: "openai/gpt-5",
      },
    ],
  },
  models: {
    providers: {
      openai: {
        baseUrl: "https://api.openai.com/v1",
        api: "openai-responses",
        apiKey: "${OPENAI_API_KEY}",
        models: [
          { id: "gpt-5", name: "GPT-5" },
        ],
      },
    },
  },
  mcp: {
    servers: {
      filesystem: {
        command: "npx",
        args: ["-y", "@modelcontextprotocol/server-filesystem", "."],
        transport: "stdio",
      },
      remote: {
        transport: "http",
        url: "https://mcp.example.com/v1",
      },
    },
  },
}`
	if err := os.WriteFile(configPath, []byte(config), 0o600); err != nil {
		t.Fatalf("failed to write test config: %v", err)
	}

	agent := AgentConfig{Name: "OpenClaw", ConfigPath: configPath}
	plan, err := buildOpenClawManagedMCPEnrollmentPlan(
		agent,
		"https://preloop.example",
		"managed-token",
	)
	if err != nil {
		t.Fatalf("buildOpenClawManagedMCPEnrollmentPlan returned error: %v", err)
	}

	servers := ensureObjectPath(plan.ManagedDocument, "mcp", "servers")
	if len(servers) != 1 {
		t.Fatalf("expected rewritten config to keep only preloop MCP, got %#v", servers)
	}
	preloopServer, ok := servers["preloop"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected preloop MCP server in managed config, got %#v", servers)
	}
	if preloopServer["url"] != "https://preloop.example/mcp/v1" {
		t.Fatalf("unexpected managed MCP URL: %#v", preloopServer)
	}

	providers := ensureObjectPath(plan.ManagedDocument, "models", "providers")
	managedProvider, ok := providers[openClawManagedProviderID].(map[string]interface{})
	if !ok {
		t.Fatalf("expected managed provider to be present, got %#v", providers)
	}
	if managedProvider["baseUrl"] != "https://preloop.example/openai/v1" {
		t.Fatalf("unexpected managed gateway URL: %#v", managedProvider)
	}
	if managedProvider["apiKey"] != "managed-token" {
		t.Fatalf("unexpected managed gateway token: %#v", managedProvider)
	}
	if extractOpenClawPrimaryModel(plan.ManagedDocument) != "preloop/openai/gpt-5" {
		t.Fatalf("expected primary model to be rewritten, got %#v", plan.ManagedDocument)
	}

	validation := openClawManagedMCPAdapter{}.ValidateManagedConfig(
		plan.ManagedDocument,
		"https://preloop.example",
	)
	if passed, _ := validation["validation_passed"].(bool); !passed {
		t.Fatalf("expected rewritten config to validate, got %#v", validation)
	}
}

func TestBuildManagedRemoteServerRequestImportsCommandBackedMCporter(t *testing.T) {
	server := MCPDef{
		Command:   "npx",
		Args:      []string{"-y", "mcporter", "--url=https://remote.example.com/mcp"},
		Transport: "stdio",
		Env: map[string]string{
			"AUTHORIZATION": "Bearer upstream-token",
		},
	}

	request, warning, importMode, ok := buildManagedRemoteServerRequest("remote", server)
	if !ok {
		t.Fatal("expected command-backed server to be imported")
	}
	if importMode != "command" {
		t.Fatalf("expected command import mode, got %q", importMode)
	}
	if request["url"] != "https://remote.example.com/mcp" {
		t.Fatalf("unexpected imported URL: %#v", request)
	}
	if request["transport"] != "http-streaming" {
		t.Fatalf("expected stdio transport to be normalized, got %#v", request)
	}
	if request["auth_type"] != "bearer" {
		t.Fatalf("expected bearer auth, got %#v", request)
	}
	authConfig, ok := request["auth_config"].(map[string]interface{})
	if !ok || authConfig["token"] != "upstream-token" {
		t.Fatalf("expected imported bearer token, got %#v", request)
	}
	if !strings.Contains(strings.ToLower(warning), "mcporter") {
		t.Fatalf("expected mcporter warning, got %q", warning)
	}
}

func TestInferOpenClawProviderNamePrefersProviderID(t *testing.T) {
	if got := inferOpenClawProviderName("google", "openai-completions"); got != "google" {
		t.Fatalf("expected google provider to remain google, got %q", got)
	}
}

func TestResolveOpenClawProviderAPIKeyFallsBackToAuthProfiles(t *testing.T) {
	document := map[string]interface{}{
		"auth": map[string]interface{}{
			"profiles": map[string]interface{}{
				"google:default": map[string]interface{}{
					"mode":     "api_key",
					"provider": "google",
				},
			},
		},
	}

	value, note := resolveOpenClawProviderAPIKey(document, "google")
	if value != "" {
		t.Fatalf("expected no resolved credential value, got %q", value)
	}
	if !strings.Contains(note, "auth.profiles") || !strings.Contains(note, "google:default") {
		t.Fatalf("expected auth profile note, got %q", note)
	}
}

func TestFilterAgentsPendingLocalEnrollmentSkipsSavedState(t *testing.T) {
	tempDir := t.TempDir()
	t.Setenv("HOME", tempDir)

	enrolled := AgentConfig{
		Name:       "OpenClaw",
		ConfigPath: filepath.Join(tempDir, ".openclaw", "openclaw.json"),
	}
	pending := AgentConfig{
		Name:       "Codex CLI",
		ConfigPath: filepath.Join(tempDir, ".codex", "config.json"),
	}

	if err := saveLocalEnrollmentState(&localEnrollmentState{
		AgentName:          enrolled.Name,
		RuntimePrincipalID: runtimePrincipalIDForAgent(enrolled),
		ConfigPath:         enrolled.ConfigPath,
		BackupPath:         filepath.Join(tempDir, "backup.json"),
		ManagedServerName:  "preloop",
		ManagedServerURL:   "https://preloop.example/mcp/v1",
		AppliedAt:          time.Now().UTC(),
	}); err != nil {
		t.Fatalf("failed to save local enrollment state: %v", err)
	}

	candidates := filterAgentsPendingLocalEnrollment([]AgentConfig{enrolled, pending})
	if len(candidates) != 1 {
		t.Fatalf("expected one onboarding candidate, got %#v", candidates)
	}
	if candidates[0].Name != pending.Name {
		t.Fatalf("expected pending agent to remain, got %#v", candidates)
	}
}

func TestDefaultManagedLiveValidationResult_ForOpenClaw(t *testing.T) {
	result := defaultManagedLiveValidationResult(AgentConfig{Name: "OpenClaw"})
	if supported, _ := result["live_validation_supported"].(bool); !supported {
		t.Fatalf("expected live validation to be supported, got %#v", result)
	}
	if status := result["live_validation_status"]; status != "not_run" {
		t.Fatalf("expected not_run status, got %#v", result)
	}
}

func TestWaitForManagedValidationUsage_FindsIndexedEvent(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.Contains(r.URL.RawQuery, "runtime_principal_id=octavia-123") {
			t.Fatalf("expected runtime principal filter in query, got %q", r.URL.RawQuery)
		}
		if !strings.Contains(r.URL.RawQuery, "api_key_id=key-1") {
			t.Fatalf("expected api key filter in query, got %q", r.URL.RawQuery)
		}
		_ = json.NewEncoder(w).Encode(gatewayUsageSearchResponse{
			Items: []gatewayUsageSearchItem{
				{
					APIUsageID:         "usage-1",
					Timestamp:          "2026-03-10T10:00:00Z",
					StatusCode:         200,
					ModelAlias:         "openai/gpt-5",
					RuntimePrincipalID: "octavia-123",
					APIKeyID:           "key-1",
				},
			},
		})
	}))
	defer server.Close()

	client := api.NewClientWithToken(server.URL, "tok")
	item, err := waitForManagedValidationUsage(
		client,
		"octavia-123",
		"key-1",
		"openai/gpt-5",
		"validation-token",
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if item == nil || item.APIUsageID != "usage-1" {
		t.Fatalf("expected indexed usage item, got %#v", item)
	}
}
