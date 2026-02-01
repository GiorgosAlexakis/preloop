// Package cmd contains all CLI commands for the preloop CLI.
package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"

	"github.com/preloop/preloop/cli/internal/version"
)

var (
	// cfgFile is the path to the config file (set via flag).
	cfgFile string

	// verbose enables verbose output.
	verbose bool
)

// rootCmd represents the base command when called without any subcommands.
var rootCmd = &cobra.Command{
	Use:   "preloop",
	Short: "Preloop CLI - Manage AI agent policies and approvals",
	Long: `Preloop CLI is a command-line interface for managing AI agent policies,
approvals, and tool configurations.

Use this CLI to:
  - Authenticate with your Preloop account
  - Manage and validate policies
  - Configure available tools
  - Review and respond to approval requests

Get started by running 'preloop auth login' to authenticate.`,
	PersistentPreRun: func(cmd *cobra.Command, args []string) {
		// Check for updates on each invocation (cached daily)
		if err := version.CheckForUpdate(); err != nil {
			// Silently ignore update check errors
			if verbose {
				fmt.Fprintf(os.Stderr, "Warning: failed to check for updates: %v\n", err)
			}
		}
	},
}

// Execute adds all child commands to the root command and sets flags appropriately.
// This is called by main.main(). It only needs to happen once to the rootCmd.
func Execute() error {
	return rootCmd.Execute()
}

func init() {
	// Global flags
	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "", "config file (default is $HOME/.preloop/config.yaml)")
	rootCmd.PersistentFlags().BoolVarP(&verbose, "verbose", "v", false, "enable verbose output")

	// Add subcommands
	rootCmd.AddCommand(authCmd)
	rootCmd.AddCommand(policyCmd)
	rootCmd.AddCommand(toolsCmd)
	rootCmd.AddCommand(approvalsCmd)
	rootCmd.AddCommand(versionCmd)
}
