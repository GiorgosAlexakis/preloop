package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"text/tabwriter"

	"github.com/spf13/cobra"
	"gopkg.in/yaml.v3"

	"github.com/preloop/preloop/cli/internal/api"
)

const (
	toolsListPath = "/api/v1/tools"
)

// Tool represents a tool configuration.
type Tool struct {
	ID          string   `json:"id" yaml:"id"`
	Name        string   `json:"name" yaml:"name"`
	Description string   `json:"description,omitempty" yaml:"description,omitempty"`
	Enabled     bool     `json:"enabled" yaml:"enabled"`
	Category    string   `json:"category,omitempty" yaml:"category,omitempty"`
	RiskLevel   string   `json:"risk_level,omitempty" yaml:"risk_level,omitempty"`
	Permissions []string `json:"permissions,omitempty" yaml:"permissions,omitempty"`
}

// toolsCmd represents the tools command group.
var toolsCmd = &cobra.Command{
	Use:   "tools",
	Short: "Manage tool configurations",
	Long:  `Manage AI agent tool configurations and permissions.`,
}

// toolsListCmd represents the tools list command.
var toolsListCmd = &cobra.Command{
	Use:   "list",
	Short: "List available tools",
	Long: `List all available tools and their current status.

Examples:
  preloop tools list
  preloop tools list --enabled
  preloop tools list --format json`,
	RunE: runToolsList,
}

// toolsEnableCmd represents the tools enable command.
var toolsEnableCmd = &cobra.Command{
	Use:   "enable <tool-name>",
	Short: "Enable a tool",
	Long: `Enable a tool for AI agents to use.

Examples:
  preloop tools enable shell-execute
  preloop tools enable file-read`,
	Args: cobra.ExactArgs(1),
	RunE: runToolsEnable,
}

// toolsDisableCmd represents the tools disable command.
var toolsDisableCmd = &cobra.Command{
	Use:   "disable <tool-name>",
	Short: "Disable a tool",
	Long: `Disable a tool, preventing AI agents from using it.

Examples:
  preloop tools disable shell-execute`,
	Args: cobra.ExactArgs(1),
	RunE: runToolsDisable,
}

func init() {
	// Add subcommands
	toolsCmd.AddCommand(toolsListCmd)
	toolsCmd.AddCommand(toolsEnableCmd)
	toolsCmd.AddCommand(toolsDisableCmd)

	// Flags for list
	toolsListCmd.Flags().Bool("enabled", false, "show only enabled tools")
	toolsListCmd.Flags().Bool("disabled", false, "show only disabled tools")
	toolsListCmd.Flags().StringP("format", "f", "table", "output format (table, json, yaml)")
	toolsListCmd.Flags().StringP("category", "c", "", "filter by category")
}

// runToolsList lists all available tools.
func runToolsList(cmd *cobra.Command, args []string) error {
	enabledOnly, _ := cmd.Flags().GetBool("enabled")
	disabledOnly, _ := cmd.Flags().GetBool("disabled")
	format, _ := cmd.Flags().GetString("format")
	category, _ := cmd.Flags().GetString("category")

	client, err := api.NewClient(FlagToken, FlagURL)
	if err != nil {
		return fmt.Errorf("failed to create API client: %w", err)
	}

	if !client.IsAuthenticated() {
		return fmt.Errorf("not authenticated - run 'preloop auth login' first")
	}

	var tools []Tool
	if err := client.Get(toolsListPath, &tools); err != nil {
		return fmt.Errorf("failed to list tools: %w", err)
	}

	// Filter tools
	var filtered []Tool
	for _, t := range tools {
		// Filter by enabled/disabled status
		if enabledOnly && !t.Enabled {
			continue
		}
		if disabledOnly && t.Enabled {
			continue
		}

		// Filter by category
		if category != "" && !strings.EqualFold(t.Category, category) {
			continue
		}

		filtered = append(filtered, t)
	}

	if len(filtered) == 0 {
		fmt.Println("No tools found matching the criteria")
		return nil
	}

	switch strings.ToLower(format) {
	case "json":
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		return enc.Encode(filtered)

	case "yaml":
		enc := yaml.NewEncoder(os.Stdout)
		return enc.Encode(filtered)

	default: // table
		w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
		fmt.Fprintln(w, "NAME\tSTATUS\tCATEGORY\tRISK\tDESCRIPTION")
		for _, t := range filtered {
			status := "disabled"
			if t.Enabled {
				status = "enabled"
			}
			desc := t.Description
			if len(desc) > 50 {
				desc = desc[:47] + "..."
			}
			fmt.Fprintf(w, "%s\t%s\t%s\t%s\t%s\n",
				t.Name, status, t.Category, t.RiskLevel, desc)
		}
		return w.Flush()
	}
}

// runToolsEnable enables a tool.
func runToolsEnable(cmd *cobra.Command, args []string) error {
	toolName := args[0]

	client, err := api.NewClient(FlagToken, FlagURL)
	if err != nil {
		return fmt.Errorf("failed to create API client: %w", err)
	}

	if !client.IsAuthenticated() {
		return fmt.Errorf("not authenticated - run 'preloop auth login' first")
	}

	// First, find the tool to get its ID
	toolID, err := findToolByName(client, toolName)
	if err != nil {
		return err
	}

	// Enable the tool
	path := fmt.Sprintf("%s/%s", toolsListPath, toolID)
	request := map[string]bool{
		"enabled": true,
	}

	var result Tool
	if err := client.Put(path, request, &result); err != nil {
		return fmt.Errorf("failed to enable tool: %w", err)
	}

	fmt.Printf("✓ Tool '%s' enabled successfully\n", result.Name)
	return nil
}

// runToolsDisable disables a tool.
func runToolsDisable(cmd *cobra.Command, args []string) error {
	toolName := args[0]

	client, err := api.NewClient(FlagToken, FlagURL)
	if err != nil {
		return fmt.Errorf("failed to create API client: %w", err)
	}

	if !client.IsAuthenticated() {
		return fmt.Errorf("not authenticated - run 'preloop auth login' first")
	}

	// First, find the tool to get its ID
	toolID, err := findToolByName(client, toolName)
	if err != nil {
		return err
	}

	// Disable the tool
	path := fmt.Sprintf("%s/%s", toolsListPath, toolID)
	request := map[string]bool{
		"enabled": false,
	}

	var result Tool
	if err := client.Put(path, request, &result); err != nil {
		return fmt.Errorf("failed to disable tool: %w", err)
	}

	fmt.Printf("✓ Tool '%s' disabled successfully\n", result.Name)
	return nil
}

// findToolByName finds a tool by name and returns its ID.
func findToolByName(client *api.Client, name string) (string, error) {
	var tools []Tool
	if err := client.Get(toolsListPath, &tools); err != nil {
		return "", fmt.Errorf("failed to list tools: %w", err)
	}

	// Try exact match first
	for _, t := range tools {
		if t.Name == name || t.ID == name {
			return t.ID, nil
		}
	}

	// Try case-insensitive match
	for _, t := range tools {
		if strings.EqualFold(t.Name, name) {
			return t.ID, nil
		}
	}

	// Build list of available tools for error message
	var available []string
	for _, t := range tools {
		available = append(available, t.Name)
	}

	return "", fmt.Errorf("tool '%s' not found. Available tools: %s",
		name, strings.Join(available, ", "))
}
