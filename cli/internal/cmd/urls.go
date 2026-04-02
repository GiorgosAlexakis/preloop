package cmd

import (
	"fmt"
	"strings"

	"github.com/preloop/preloop/cli/internal/config"
)

func resolveConfiguredURLs() (string, string, error) {
	cfg, err := config.ResolveWithOverrides(FlagToken, FlagURL, FlagAPIURL)
	if err != nil {
		return "", "", fmt.Errorf("failed to load config: %w", err)
	}

	apiURL := strings.TrimRight(cfg.APIURL, "/")
	publicURL := strings.TrimRight(cfg.PublicURL, "/")
	return apiURL, publicURL, nil
}

func resolveConfiguredAPIURL() (string, error) {
	apiURL, _, err := resolveConfiguredURLs()
	return apiURL, err
}

func resolveConfiguredPublicURL() (string, error) {
	_, publicURL, err := resolveConfiguredURLs()
	return publicURL, err
}
