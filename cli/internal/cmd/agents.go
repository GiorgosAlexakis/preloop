package cmd

import (
	"crypto/sha1"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"os/user"
	"path/filepath"
	"sort"
	"strings"

	"github.com/spf13/cobra"

	"github.com/preloop/preloop/cli/internal/api"
)

// AgentConfig describes a discovered AI agent MCP configuration.
type AgentConfig struct {
	Name       string            `json:"name"`
	ConfigPath string            `json:"config_path"`
	MCPServers map[string]MCPDef `json:"mcp_servers,omitempty"`
}

// MCPDef is a minimal MCP server definition read from an agent config.
type MCPDef struct {
	Command string            `json:"command,omitempty"`
	Args    []string          `json:"args,omitempty"`
	URL     string            `json:"url,omitempty"`
	Env     map[string]string `json:"env,omitempty"`
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
		ConfigPaths: []string{".claude/claude_desktop_config.json", ".config/claude/claude_desktop_config.json"},
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
		Name:        "OpenClaw",
		ConfigPaths: []string{".openclaw/openclaw.json"},
		Parser:      parseGenericMCP,
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
	Long: `Scan standard configuration paths for known AI agents, display their
MCP server configurations, and optionally add their MCP servers to your
Preloop account and issue runtime-scoped session tokens.

Supported agents: Claude Code, Cursor, Windsurf, VSCode/Copilot,
                  Gemini CLI, OpenCode, Codex CLI, OpenClaw.

Examples:
  preloop agents discover
  preloop agents discover --add
  preloop agents discover --json`,
	RunE: runAgentsDiscover,
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
	agentsCmd.AddCommand(agentsStarterPolicyCmd)

	agentsDiscoverCmd.Flags().Bool("add", false, "interactively add discovered MCP servers to your Preloop account")
	agentsDiscoverCmd.Flags().Bool("json", false, "output discovered agents as JSON")
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

	home, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("could not determine home directory: %w", err)
	}

	var discovered []AgentConfig

	for _, spec := range agentSpecs {
		for _, relPath := range spec.ConfigPaths {
			fullPath := filepath.Join(home, relPath)
			if _, err := os.Stat(fullPath); err != nil {
				continue
			}

			servers, err := spec.Parser(fullPath)
			if err != nil {
				if !asJSON {
					fmt.Printf("  ⚠ Could not parse %s config at %s: %v\n", spec.Name, fullPath, err)
				}
				continue
			}

			discovered = append(discovered, AgentConfig{
				Name:       spec.Name,
				ConfigPath: fullPath,
				MCPServers: servers,
			})
			break // first match wins per agent
		}
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

	if addServers && totalServers > 0 {
		return addDiscoveredServers(discovered)
	}

	if totalServers > 0 && !addServers {
		fmt.Println("Tip: Use --add to interactively add these servers to your Preloop account.")
	}

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
		SessionSourceID:      runtimeSessionSourceIDForAgent(agent),
		SessionReference:     filepath.Clean(agent.ConfigPath),
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

func runtimeSessionSourceIDForAgent(agent AgentConfig) string {
	sum := sha1.Sum([]byte(strings.ToLower(agent.Name) + "\x00" + filepath.Clean(agent.ConfigPath)))
	prefix := strings.ToLower(agent.Name)
	replacer := strings.NewReplacer(" ", "-", "/", "-", "\\", "-", ":", "-", ".", "-")
	prefix = strings.Trim(replacer.Replace(prefix), "-")
	if prefix == "" {
		prefix = "agent"
	}
	return fmt.Sprintf("%s-%s", prefix, hex.EncodeToString(sum[:6]))
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

	var config struct {
		MCPServers map[string]json.RawMessage `json:"mcpServers"`
	}
	if err := json.Unmarshal(data, &config); err != nil {
		return nil, err
	}

	result := make(map[string]MCPDef)
	for name, raw := range config.MCPServers {
		var def MCPDef
		if err := json.Unmarshal(raw, &def); err != nil {
			continue
		}
		result[name] = def
	}
	return result, nil
}

// parseGenericMCP reads configs with a top-level "mcpServers" key.
func parseGenericMCP(path string) (map[string]MCPDef, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	// Try mcpServers key first (Cursor, Windsurf, Codex, OpenClaw)
	var config struct {
		MCPServers map[string]json.RawMessage `json:"mcpServers"`
		Servers    map[string]json.RawMessage `json:"servers"`
	}
	if err := json.Unmarshal(data, &config); err != nil {
		return nil, err
	}

	servers := config.MCPServers
	if servers == nil {
		servers = config.Servers
	}

	result := make(map[string]MCPDef)
	for name, raw := range servers {
		var def MCPDef
		if err := json.Unmarshal(raw, &def); err != nil {
			continue
		}
		result[name] = def
	}
	return result, nil
}

// parseGeminiConfig reads Gemini CLI's settings.json format.
func parseGeminiConfig(path string) (map[string]MCPDef, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}

	var config struct {
		MCPServers map[string]json.RawMessage `json:"mcpServers"`
	}
	if err := json.Unmarshal(data, &config); err != nil {
		return nil, err
	}

	result := make(map[string]MCPDef)
	for name, raw := range config.MCPServers {
		var def MCPDef
		if err := json.Unmarshal(raw, &def); err != nil {
			continue
		}
		result[name] = def
	}
	return result, nil
}
