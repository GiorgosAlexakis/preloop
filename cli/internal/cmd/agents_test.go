package cmd

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

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
