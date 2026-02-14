package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"text/tabwriter"

	"github.com/spf13/cobra"
	"gopkg.in/yaml.v3"

	"github.com/preloop/preloop/cli/internal/api"
)

const (
	policiesValidatePath = "/api/v1/policies/validate"
	policiesUploadPath   = "/api/v1/policies/upload"
	policiesDiffPath     = "/api/v1/policies/diff"
	policiesExportPath   = "/api/v1/policies/export"
	policiesListPath     = "/api/v1/policies"
)

// PolicyFile represents a policy file for upload.
type PolicyFile struct {
	Name    string `json:"name" yaml:"name"`
	Content string `json:"content" yaml:"-"`
}

// ValidationResult represents the result of policy validation.
type ValidationResult struct {
	Valid    bool              `json:"valid"`
	Errors   []ValidationError `json:"errors,omitempty"`
	Warnings []string          `json:"warnings,omitempty"`
}

// ValidationError represents a validation error.
type ValidationError struct {
	Line    int    `json:"line,omitempty"`
	Column  int    `json:"column,omitempty"`
	Message string `json:"message"`
	Path    string `json:"path,omitempty"`
}

// PolicyDiff represents the diff between local and remote policy.
type PolicyDiff struct {
	HasChanges bool         `json:"has_changes"`
	Added      []string     `json:"added,omitempty"`
	Removed    []string     `json:"removed,omitempty"`
	Modified   []DiffChange `json:"modified,omitempty"`
}

// DiffChange represents a single change in the diff.
type DiffChange struct {
	Path     string `json:"path"`
	OldValue string `json:"old_value,omitempty"`
	NewValue string `json:"new_value,omitempty"`
}

// PolicyInfo represents a policy in the list response.
type PolicyInfo struct {
	ID          string `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description,omitempty"`
	Version     string `json:"version,omitempty"`
	Active      bool   `json:"active"`
	UpdatedAt   string `json:"updated_at"`
}

// policyCmd represents the policy command group.
var policyCmd = &cobra.Command{
	Use:   "policy",
	Short: "Manage policies",
	Long:  `Manage AI agent policies for your organization.`,
}

// policyValidateCmd represents the policy validate command.
var policyValidateCmd = &cobra.Command{
	Use:   "validate <file>",
	Short: "Validate a policy file",
	Long: `Validate a policy YAML file for syntax and semantic correctness.

The validation is performed both locally and against the API to ensure
the policy is valid and compatible with the current version.

Examples:
  preloop policy validate my-policy.yaml
  preloop policy validate ./policies/security.yaml`,
	Args: cobra.ExactArgs(1),
	RunE: runPolicyValidate,
}

// policyApplyCmd represents the policy apply command.
var policyApplyCmd = &cobra.Command{
	Use:   "apply <file>",
	Short: "Apply a policy to Preloop",
	Long: `Apply a policy file to your Preloop organization.

This will upload and activate the policy on the server.

Examples:
  preloop policy apply my-policy.yaml
  preloop policy apply ./policies/ --recursive`,
	Args: cobra.ExactArgs(1),
	RunE: runPolicyApply,
}

// policyDiffCmd represents the policy diff command.
var policyDiffCmd = &cobra.Command{
	Use:   "diff <file>",
	Short: "Show differences between local and remote policy",
	Long: `Compare a local policy file with the version currently on the server.

This shows what would change if you applied the local policy.

Examples:
  preloop policy diff my-policy.yaml`,
	Args: cobra.ExactArgs(1),
	RunE: runPolicyDiff,
}

// policyExportCmd represents the policy export command.
var policyExportCmd = &cobra.Command{
	Use:   "export",
	Short: "Export current policy from Preloop",
	Long: `Export the current policy from your Preloop organization to a local file.

Examples:
  preloop policy export
  preloop policy export -o policy.yaml`,
	RunE: runPolicyExport,
}

// policyListCmd represents the policy list command.
var policyListCmd = &cobra.Command{
	Use:   "list",
	Short: "List all policies",
	Long:  `List all policies in your Preloop organization.`,
	RunE:  runPolicyList,
}

func init() {
	// Add subcommands
	policyCmd.AddCommand(policyValidateCmd)
	policyCmd.AddCommand(policyApplyCmd)
	policyCmd.AddCommand(policyDiffCmd)
	policyCmd.AddCommand(policyExportCmd)
	policyCmd.AddCommand(policyListCmd)

	// Flags for apply
	policyApplyCmd.Flags().Bool("dry-run", false, "validate and show what would be applied without making changes")
	policyApplyCmd.Flags().BoolP("recursive", "r", false, "recursively apply policies from directory")

	// Flags for export
	policyExportCmd.Flags().StringP("output", "o", "", "output file (default: stdout)")

	// Flags for list
	policyListCmd.Flags().StringP("format", "f", "table", "output format (table, json, yaml)")
}

// runPolicyValidate validates a policy file.
func runPolicyValidate(cmd *cobra.Command, args []string) error {
	filePath := args[0]

	// Read the policy file
	content, err := os.ReadFile(filePath)
	if err != nil {
		return fmt.Errorf("failed to read file: %w", err)
	}

	// Local YAML syntax validation
	var parsed interface{}
	if err := yaml.Unmarshal(content, &parsed); err != nil {
		fmt.Printf("✗ Invalid YAML syntax in %s\n", filePath)
		fmt.Printf("  Error: %v\n", err)
		return fmt.Errorf("YAML validation failed")
	}

	fmt.Printf("✓ Valid YAML syntax: %s\n", filePath)

	// API validation
	client, err := api.NewClient(FlagToken, FlagURL)
	if err != nil {
		return fmt.Errorf("failed to create API client: %w", err)
	}

	if !client.IsAuthenticated() {
		fmt.Println("\nNote: Skipping API validation (not authenticated)")
		fmt.Println("Run 'preloop auth login' for full validation")
		return nil
	}

	request := map[string]string{
		"name":    filepath.Base(filePath),
		"content": string(content),
	}

	var result ValidationResult
	if err := client.Post(policiesValidatePath, request, &result); err != nil {
		return fmt.Errorf("API validation failed: %w", err)
	}

	if !result.Valid {
		fmt.Printf("\n✗ Policy validation failed\n")
		for _, e := range result.Errors {
			if e.Line > 0 {
				fmt.Printf("  Line %d: %s\n", e.Line, e.Message)
			} else if e.Path != "" {
				fmt.Printf("  %s: %s\n", e.Path, e.Message)
			} else {
				fmt.Printf("  %s\n", e.Message)
			}
		}
		return fmt.Errorf("validation failed with %d errors", len(result.Errors))
	}

	fmt.Printf("✓ API validation passed\n")

	if len(result.Warnings) > 0 {
		fmt.Printf("\nWarnings:\n")
		for _, w := range result.Warnings {
			fmt.Printf("  ⚠ %s\n", w)
		}
	}

	return nil
}

// runPolicyApply applies a policy file.
func runPolicyApply(cmd *cobra.Command, args []string) error {
	filePath := args[0]
	dryRun, _ := cmd.Flags().GetBool("dry-run")

	// Read the policy file
	content, err := os.ReadFile(filePath)
	if err != nil {
		return fmt.Errorf("failed to read file: %w", err)
	}

	// Validate YAML syntax first
	var parsed interface{}
	if err := yaml.Unmarshal(content, &parsed); err != nil {
		return fmt.Errorf("invalid YAML syntax: %w", err)
	}

	client, err := api.NewClient(FlagToken, FlagURL)
	if err != nil {
		return fmt.Errorf("failed to create API client: %w", err)
	}

	if !client.IsAuthenticated() {
		return fmt.Errorf("not authenticated - run 'preloop auth login' first")
	}

	// If dry-run, just validate
	if dryRun {
		fmt.Printf("Dry run - validating policy: %s\n\n", filePath)

		request := map[string]string{
			"name":    filepath.Base(filePath),
			"content": string(content),
		}

		var result ValidationResult
		if err := client.Post(policiesValidatePath, request, &result); err != nil {
			return fmt.Errorf("validation failed: %w", err)
		}

		if !result.Valid {
			fmt.Printf("✗ Policy validation failed\n")
			for _, e := range result.Errors {
				fmt.Printf("  %s\n", e.Message)
			}
			return fmt.Errorf("validation failed")
		}

		fmt.Printf("✓ Policy is valid and would be applied\n")
		return nil
	}

	// Upload and apply the policy
	fmt.Printf("Applying policy: %s\n", filePath)

	request := map[string]string{
		"name":    filepath.Base(filePath),
		"content": string(content),
	}

	var result struct {
		ID      string `json:"id"`
		Message string `json:"message"`
	}

	if err := client.Post(policiesUploadPath, request, &result); err != nil {
		return fmt.Errorf("failed to apply policy: %w", err)
	}

	fmt.Printf("✓ Policy applied successfully\n")
	if result.ID != "" {
		fmt.Printf("  Policy ID: %s\n", result.ID)
	}
	if result.Message != "" {
		fmt.Printf("  %s\n", result.Message)
	}

	return nil
}

// runPolicyDiff shows the difference between local and remote policy.
func runPolicyDiff(cmd *cobra.Command, args []string) error {
	filePath := args[0]

	// Read the policy file
	content, err := os.ReadFile(filePath)
	if err != nil {
		return fmt.Errorf("failed to read file: %w", err)
	}

	client, err := api.NewClient(FlagToken, FlagURL)
	if err != nil {
		return fmt.Errorf("failed to create API client: %w", err)
	}

	if !client.IsAuthenticated() {
		return fmt.Errorf("not authenticated - run 'preloop auth login' first")
	}

	request := map[string]string{
		"name":    filepath.Base(filePath),
		"content": string(content),
	}

	var diff PolicyDiff
	if err := client.Post(policiesDiffPath, request, &diff); err != nil {
		return fmt.Errorf("failed to compute diff: %w", err)
	}

	if !diff.HasChanges {
		fmt.Println("No changes detected - local policy matches remote")
		return nil
	}

	fmt.Printf("Changes for: %s\n\n", filePath)

	if len(diff.Added) > 0 {
		fmt.Println("Added:")
		for _, item := range diff.Added {
			fmt.Printf("  + %s\n", item)
		}
		fmt.Println()
	}

	if len(diff.Removed) > 0 {
		fmt.Println("Removed:")
		for _, item := range diff.Removed {
			fmt.Printf("  - %s\n", item)
		}
		fmt.Println()
	}

	if len(diff.Modified) > 0 {
		fmt.Println("Modified:")
		for _, change := range diff.Modified {
			fmt.Printf("  ~ %s\n", change.Path)
			if change.OldValue != "" {
				fmt.Printf("    - %s\n", change.OldValue)
			}
			if change.NewValue != "" {
				fmt.Printf("    + %s\n", change.NewValue)
			}
		}
	}

	return nil
}

// runPolicyExport exports the current policy from the server.
func runPolicyExport(cmd *cobra.Command, args []string) error {
	output, _ := cmd.Flags().GetString("output")

	client, err := api.NewClient(FlagToken, FlagURL)
	if err != nil {
		return fmt.Errorf("failed to create API client: %w", err)
	}

	if !client.IsAuthenticated() {
		return fmt.Errorf("not authenticated - run 'preloop auth login' first")
	}

	var result struct {
		Content string `json:"content"`
	}

	if err := client.Get(policiesExportPath, &result); err != nil {
		return fmt.Errorf("failed to export policy: %w", err)
	}

	if output != "" {
		if err := os.WriteFile(output, []byte(result.Content), 0644); err != nil {
			return fmt.Errorf("failed to write file: %w", err)
		}
		fmt.Printf("Policy exported to: %s\n", output)
	} else {
		fmt.Print(result.Content)
	}

	return nil
}

// runPolicyList lists all policies.
func runPolicyList(cmd *cobra.Command, args []string) error {
	format, _ := cmd.Flags().GetString("format")

	client, err := api.NewClient(FlagToken, FlagURL)
	if err != nil {
		return fmt.Errorf("failed to create API client: %w", err)
	}

	if !client.IsAuthenticated() {
		return fmt.Errorf("not authenticated - run 'preloop auth login' first")
	}

	var policies []PolicyInfo
	if err := client.Get(policiesListPath, &policies); err != nil {
		return fmt.Errorf("failed to list policies: %w", err)
	}

	if len(policies) == 0 {
		fmt.Println("No policies found")
		return nil
	}

	switch strings.ToLower(format) {
	case "json":
		enc := json.NewEncoder(os.Stdout)
		enc.SetIndent("", "  ")
		return enc.Encode(policies)

	case "yaml":
		enc := yaml.NewEncoder(os.Stdout)
		return enc.Encode(policies)

	default: // table
		w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
		fmt.Fprintln(w, "NAME\tVERSION\tACTIVE\tUPDATED")
		for _, p := range policies {
			active := "no"
			if p.Active {
				active = "yes"
			}
			fmt.Fprintf(w, "%s\t%s\t%s\t%s\n", p.Name, p.Version, active, p.UpdatedAt)
		}
		return w.Flush()
	}
}
