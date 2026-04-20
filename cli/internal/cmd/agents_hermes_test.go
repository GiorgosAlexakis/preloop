package cmd

import (
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
