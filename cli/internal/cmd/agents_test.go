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

func TestFindStarterPolicyTools_CaseInsensitiveServerMatch(t *testing.T) {
	tools := []starterPolicyTool{
		{Name: "list_repos", Source: "mcp", SourceID: "srv-1", SourceName: "GitHub"},
		{Name: "create_issue", Source: "mcp", SourceID: "srv-1", SourceName: "GitHub"},
		{Name: "get_issue", Source: "builtin", SourceName: "Built-in"},
	}

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(tools)
	}))
	defer server.Close()

	client := api.NewClientWithToken(server.URL, "tok")
	matchedName, filtered, err := findStarterPolicyTools(client, "github")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if matchedName != "GitHub" {
		t.Fatalf("expected canonical server name GitHub, got %q", matchedName)
	}
	if len(filtered) != 2 {
		t.Fatalf("expected 2 tools, got %d", len(filtered))
	}
	if filtered[0].Name != "create_issue" || filtered[1].Name != "list_repos" {
		t.Fatalf("expected sorted MCP tools, got %+v", filtered)
	}
}

func TestFindStarterPolicyTools_NotFoundIncludesAvailableServers(t *testing.T) {
	tools := []starterPolicyTool{
		{Name: "list_repos", Source: "mcp", SourceName: "GitHub"},
		{Name: "search_docs", Source: "mcp", SourceName: "Docs"},
	}

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(tools)
	}))
	defer server.Close()

	client := api.NewClientWithToken(server.URL, "tok")
	_, _, err := findStarterPolicyTools(client, "missing")
	if err == nil {
		t.Fatal("expected an error")
	}

	errMsg := err.Error()
	if !strings.Contains(errMsg, "GitHub") || !strings.Contains(errMsg, "Docs") {
		t.Fatalf("expected available servers in error, got %q", errMsg)
	}
}

func TestBuildStarterPolicyPrompt_IncludesToolSummaries(t *testing.T) {
	tools := []starterPolicyTool{
		{
			Name:        "delete_repo",
			Description: "Delete a repository",
			Source:      "mcp",
			SourceName:  "GitHub",
			Schema: map[string]interface{}{
				"properties": map[string]interface{}{
					"owner": map[string]interface{}{},
					"repo":  map[string]interface{}{},
				},
				"required": []interface{}{"owner", "repo"},
			},
			AccessRules: []starterPolicyAccessRule{
				{Action: "require_approval", ConditionType: "simple"},
			},
		},
	}

	prompt := buildStarterPolicyPrompt("GitHub", tools)

	for _, expected := range []string{
		`MCP server "GitHub"`,
		"delete_repo: Delete a repository",
		"Suggested posture: require approval",
		"Args: owner, repo",
		"Required args: owner, repo",
		"Existing rules: require_approval (simple)",
	} {
		if !strings.Contains(prompt, expected) {
			t.Fatalf("expected prompt to contain %q, got:\n%s", expected, prompt)
		}
	}
}

func TestDefaultStarterPolicyFileName(t *testing.T) {
	if got := defaultStarterPolicyFileName("GitHub Enterprise"); got != "github-enterprise-starter-policy.yaml" {
		t.Fatalf("unexpected file name: %q", got)
	}
}

func TestRuntimeSessionSourceTypeForAgent(t *testing.T) {
	cases := map[string]string{
		"Claude Code":    "claude_code",
		"Claude Desktop": "claude_desktop",
		"Codex CLI":      "codex",
		"OpenClaw":       "openclaw",
		"Cursor":         "desktop_agent",
	}

	for agentName, want := range cases {
		if got := runtimeSessionSourceTypeForAgent(agentName); got != want {
			t.Fatalf("agent %q: expected %q, got %q", agentName, want, got)
		}
	}
}

func TestRuntimePrincipalIDForAgent_IsStable(t *testing.T) {
	agent := AgentConfig{
		Name:       "Claude Code",
		ConfigPath: filepath.Join("/tmp", "workspace", "claude_desktop_config.json"),
	}

	got1 := runtimePrincipalIDForAgent(agent)
	got2 := runtimePrincipalIDForAgent(agent)
	if got1 != got2 {
		t.Fatalf("expected stable source id, got %q and %q", got1, got2)
	}
	if !strings.HasPrefix(got1, "claude-code-") {
		t.Fatalf("expected slugged prefix, got %q", got1)
	}
}

func TestRuntimeSessionInstanceIDForAgent_UsesPrincipalPrefix(t *testing.T) {
	agent := AgentConfig{
		Name:       "Claude Code",
		ConfigPath: filepath.Join("/tmp", "workspace", "claude_desktop_config.json"),
	}

	principalID := runtimePrincipalIDForAgent(agent)
	sessionID := runtimeSessionInstanceIDForAgent(agent)
	if !strings.HasPrefix(sessionID, principalID+"-") {
		t.Fatalf("expected session id %q to use principal prefix %q", sessionID, principalID)
	}
}

func TestIssueRuntimeSessionToken(t *testing.T) {
	var capturedPath string
	var capturedBody runtimeSessionTokenRequest

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedPath = r.URL.Path
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewDecoder(r.Body).Decode(&capturedBody); err != nil {
			t.Fatalf("failed to decode request body: %v", err)
		}
		_ = json.NewEncoder(w).Encode(runtimeSessionTokenResponse{
			RuntimeSessionID:  "session-1",
			Token:             "token-123",
			ExpiresAt:         "2026-03-10T12:00:00Z",
			SessionSourceType: "claude_code",
			SessionSourceID:   "claude-code-abc123",
			SessionReference:  "/tmp/workspace/claude_desktop_config.json",
		})
	}))
	defer server.Close()

	client := api.NewClientWithToken(server.URL, "tok")
	agent := AgentConfig{
		Name:       "Claude Code",
		ConfigPath: "/tmp/workspace/claude_desktop_config.json",
	}

	result, err := issueRuntimeSessionToken(client, agent, []string{"github", "jira"})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if capturedPath != "/api/v1/auth/runtime-sessions/token" {
		t.Fatalf("unexpected path: %q", capturedPath)
	}
	if capturedBody.SessionSourceType != "claude_code" {
		t.Fatalf("unexpected session source type: %q", capturedBody.SessionSourceType)
	}
	if capturedBody.RuntimePrincipalName != "Claude Code (claude_desktop_config.json)" {
		t.Fatalf("unexpected principal name: %q", capturedBody.RuntimePrincipalName)
	}
	if capturedBody.RuntimePrincipalID == "" {
		t.Fatal("expected runtime principal id to be set")
	}
	if !strings.HasPrefix(capturedBody.SessionSourceID, capturedBody.RuntimePrincipalID+"-") {
		t.Fatalf("expected session source id %q to use principal id prefix %q", capturedBody.SessionSourceID, capturedBody.RuntimePrincipalID)
	}
	if len(capturedBody.AllowedMCPServers) != 2 || capturedBody.AllowedMCPServers[0] != "github" || capturedBody.AllowedMCPServers[1] != "jira" {
		t.Fatalf("unexpected allowed servers: %+v", capturedBody.AllowedMCPServers)
	}
	if result.Token != "token-123" {
		t.Fatalf("unexpected token result: %+v", result)
	}
}

func TestParseGenericMCP_NestedMCPServers(t *testing.T) {
	dir := t.TempDir()
	configPath := filepath.Join(dir, "openclaw.json")
	if err := os.WriteFile(configPath, []byte(`{
  "mcp": {
    "servers": {
      "preloop": {
        "url": "https://preloop.ai/mcp/v1",
        "transport": "http",
        "headers": {
          "Authorization": "Bearer test-token"
        }
      }
    }
  }
}`), 0644); err != nil {
		t.Fatalf("failed to write config: %v", err)
	}

	servers, err := parseGenericMCP(configPath)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	preloop, ok := servers["preloop"]
	if !ok {
		t.Fatalf("expected preloop server, got %+v", servers)
	}
	if preloop.Transport != "http" {
		t.Fatalf("expected transport http, got %q", preloop.Transport)
	}
	if preloop.Headers["Authorization"] != "Bearer test-token" {
		t.Fatalf("unexpected headers: %+v", preloop.Headers)
	}
}

func TestFilterAgentsPendingEnrollmentSkipsRemoteManagedAgent(t *testing.T) {
	managedAgent := managedAgentListResponse{
		Items: []managedAgentSummary{
			{
				ID:                "agent-1",
				DisplayName:       "OpenClaw",
				SessionSourceType: "openclaw",
				SessionSourceID:   runtimePrincipalIDForAgent(AgentConfig{Name: "OpenClaw", ConfigPath: "/tmp/openclaw.json"}),
				LifecycleState:    "active",
			},
		},
	}

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(managedAgent)
	}))
	defer server.Close()

	client := api.NewClientWithToken(server.URL, "tok")
	discovered := []AgentConfig{
		{Name: "OpenClaw", ConfigPath: "/tmp/openclaw.json"},
		{Name: "Codex CLI", ConfigPath: "/tmp/codex.json"},
	}

	candidates, err := filterAgentsPendingEnrollment(client, discovered)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(candidates) != 1 || candidates[0].Name != "Codex CLI" {
		t.Fatalf("expected only the unenrolled agent to remain, got %#v", candidates)
	}
}

func TestBuildManagedMCPEnrollmentPlan_AddsPreloopAndRedactsSecrets(t *testing.T) {
	dir := t.TempDir()
	configPath := filepath.Join(dir, "settings.json")
	if err := os.WriteFile(configPath, []byte(`{
  "mcpServers": {
    "github": {
      "url": "https://github.example/mcp",
      "headers": {
        "Authorization": "Bearer upstream-secret"
      }
    }
  }
}`), 0644); err != nil {
		t.Fatalf("failed to write config: %v", err)
	}

	plan, err := buildManagedMCPEnrollmentPlan(AgentConfig{
		Name:       "Gemini CLI",
		ConfigPath: configPath,
		MCPServers: map[string]MCPDef{},
	}, "https://preloop.example", "durable-secret-token")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	managedServers := plan.ManagedDocument["mcpServers"].(map[string]interface{})
	preloop := managedServers["preloop"].(map[string]interface{})
	headers := preloop["headers"].(map[string]interface{})
	if headers["Authorization"] != "Bearer durable-secret-token" {
		t.Fatalf("expected durable token in managed config, got %+v", headers)
	}

	sanitizedServers := plan.SanitizedManaged["mcpServers"].(map[string]interface{})
	sanitizedPreloop := sanitizedServers["preloop"].(map[string]interface{})
	sanitizedHeaders := sanitizedPreloop["headers"].(map[string]interface{})
	if sanitizedHeaders["Authorization"] != "<redacted>" {
		t.Fatalf("expected redacted managed auth header, got %+v", sanitizedHeaders)
	}

	sanitizedExisting := sanitizedServers["github"].(map[string]interface{})
	existingHeaders := sanitizedExisting["headers"].(map[string]interface{})
	if existingHeaders["Authorization"] != "<redacted>" {
		t.Fatalf("expected redacted upstream auth header, got %+v", existingHeaders)
	}
}

func TestBuildManagedMCPEnrollmentPlan_OpenClawUsesNestedHTTPServer(t *testing.T) {
	dir := t.TempDir()
	configPath := filepath.Join(dir, "openclaw.json")
	if err := os.WriteFile(configPath, []byte(`{
  "mcp": {
    "servers": {
      "github": {
        "url": "https://github.example/mcp",
        "transport": "http"
      }
    }
  }
}`), 0644); err != nil {
		t.Fatalf("failed to write config: %v", err)
	}

	plan, err := buildManagedMCPEnrollmentPlan(AgentConfig{
		Name:       "OpenClaw",
		ConfigPath: configPath,
	}, "https://preloop.example", "openclaw-durable-token")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	mcp := plan.ManagedDocument["mcp"].(map[string]interface{})
	servers := mcp["servers"].(map[string]interface{})
	preloop := servers["preloop"].(map[string]interface{})
	if preloop["transport"] != "http" {
		t.Fatalf("expected OpenClaw transport http, got %+v", preloop)
	}
	if preloop["url"] != "https://preloop.example/mcp/v1" {
		t.Fatalf("unexpected OpenClaw managed URL: %+v", preloop)
	}
	headers := preloop["headers"].(map[string]interface{})
	if headers["Authorization"] != "Bearer openclaw-durable-token" {
		t.Fatalf("unexpected OpenClaw auth header: %+v", headers)
	}
}

func TestLocalEnrollmentStateRoundTrip(t *testing.T) {
	home := t.TempDir()
	oldHome := os.Getenv("HOME")
	if err := os.Setenv("HOME", home); err != nil {
		t.Fatalf("failed to set HOME: %v", err)
	}
	defer func() {
		_ = os.Setenv("HOME", oldHome)
	}()

	agent := AgentConfig{
		Name:       "Claude Code",
		ConfigPath: filepath.Join(home, ".claude", "mcp-servers.json"),
	}
	state := &localEnrollmentState{
		AgentName:          "Claude Code",
		RuntimePrincipalID: runtimePrincipalIDForAgent(agent),
		ConfigPath:         agent.ConfigPath,
		BackupPath:         filepath.Join(home, ".preloop", "agents", "backups", "claude-code-abc123", "backup.json"),
		ManagedServerName:  "preloop",
		ManagedServerURL:   "https://preloop.ai/mcp/v1",
		AppliedAt:          time.Now().UTC().Round(time.Second),
	}
	if err := saveLocalEnrollmentState(state); err != nil {
		t.Fatalf("failed to save local enrollment state: %v", err)
	}

	loaded, err := loadLocalEnrollmentState(agent)
	if err != nil {
		t.Fatalf("failed to load local enrollment state: %v", err)
	}
	if loaded.BackupPath != state.BackupPath {
		t.Fatalf("expected backup path %q, got %q", state.BackupPath, loaded.BackupPath)
	}
	if loaded.ManagedServerURL != state.ManagedServerURL {
		t.Fatalf("expected managed server URL %q, got %q", state.ManagedServerURL, loaded.ManagedServerURL)
	}
}

func TestLookupMCPServerContainerSupportsNestedConfig(t *testing.T) {
	container := lookupMCPServerContainer(map[string]interface{}{
		"mcp": map[string]interface{}{
			"servers": map[string]interface{}{
				"preloop": map[string]interface{}{
					"url": "https://preloop.ai/mcp/v1",
				},
			},
		},
	})

	preloop, ok := container["preloop"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected nested preloop server, got %+v", container)
	}
	if preloop["url"] != "https://preloop.ai/mcp/v1" {
		t.Fatalf("unexpected preloop server: %+v", preloop)
	}
}

func TestOpenClawAdapterValidateManagedConfig(t *testing.T) {
	adapter := managedMCPAdapterForAgent(AgentConfig{Name: "OpenClaw"})
	result := adapter.ValidateManagedConfig(map[string]interface{}{
		"mcp": map[string]interface{}{
			"servers": map[string]interface{}{
				"preloop": map[string]interface{}{
					"transport": "http",
					"url":       "https://preloop.example/mcp/v1",
					"headers": map[string]interface{}{
						"Authorization": "Bearer durable-token",
					},
				},
			},
		},
		"models": map[string]interface{}{
			"providers": map[string]interface{}{
				"preloop": map[string]interface{}{
					"baseUrl": "https://preloop.example/openai/v1",
					"api":     "openai-responses",
				},
			},
		},
		"agents": map[string]interface{}{
			"defaults": map[string]interface{}{
				"model": map[string]interface{}{
					"primary": "preloop/openai/gpt-5",
				},
			},
		},
	}, "https://preloop.example")

	if result["adapter_key"] != "openclaw" {
		t.Fatalf("expected OpenClaw adapter key, got %+v", result)
	}
	if result["nested_mcp_servers_ok"] != true {
		t.Fatalf("expected nested mcp.servers validation, got %+v", result)
	}
	if result["transport_ok"] != true || result["authorization_header_ok"] != true {
		t.Fatalf("expected OpenClaw validation to pass, got %+v", result)
	}
	if result["validation_passed"] != true {
		t.Fatalf("expected OpenClaw validation to pass, got %+v", result)
	}
}
