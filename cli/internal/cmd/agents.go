package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"os/user"
	"path/filepath"
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
Preloop account and issue scoped API keys.

Supported agents: Claude Code, Cursor, Windsurf, VSCode/Copilot,
                  Gemini CLI, OpenCode, Codex CLI, OpenClaw.

Examples:
  preloop agents discover
  preloop agents discover --add
  preloop agents discover --json`,
	RunE: runAgentsDiscover,
}

func init() {
	agentsCmd.AddCommand(agentsDiscoverCmd)

	agentsDiscoverCmd.Flags().Bool("add", false, "interactively add discovered MCP servers to your Preloop account")
	agentsDiscoverCmd.Flags().Bool("json", false, "output discovered agents as JSON")
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
		for name, server := range agent.MCPServers {
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

			// Offer to create a scoped API key
			fmt.Printf("  Issue a scoped API key for %s agent '%s'? (y/N): ", agent.Name, name)
			fmt.Scanln(&answer)

			if strings.ToLower(strings.TrimSpace(answer)) == "y" {
				keyRequest := map[string]interface{}{
					"name":   fmt.Sprintf("agent:%s:%s", agent.Name, name),
					"scopes": []string{"mcp:proxy", "tools:read"},
				}
				var keyResult struct {
					Key string `json:"key"`
				}
				if err := client.Post("/api/v1/api-keys", keyRequest, &keyResult); err != nil {
					fmt.Printf("  ✗ Failed to create API key: %v\n", err)
				} else {
					fmt.Printf("  🔑 API Key: %s\n", keyResult.Key)
					fmt.Println("     Store this key securely — it won't be shown again.")
				}
			}
		}
	}

	return nil
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
