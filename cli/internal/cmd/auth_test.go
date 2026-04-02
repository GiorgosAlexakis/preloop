package cmd

import (
	"os"
	"testing"
)

func TestResolveConfiguredAPIURLUsesEnvVariable(t *testing.T) {
	tempHome := t.TempDir()
	t.Setenv("HOME", tempHome)
	t.Setenv("PRELOOP_URL", "http://example.test/api/")

	originalFlagURL := FlagURL
	originalFlagAPIURL := FlagAPIURL
	originalFlagToken := FlagToken
	FlagURL = ""
	FlagAPIURL = ""
	FlagToken = ""
	t.Cleanup(func() {
		FlagURL = originalFlagURL
		FlagAPIURL = originalFlagAPIURL
		FlagToken = originalFlagToken
	})

	baseURL, err := resolveConfiguredAPIURL()
	if err != nil {
		t.Fatalf("resolveConfiguredAPIURL returned error: %v", err)
	}
	if baseURL != "http://example.test/api" {
		t.Fatalf("expected PRELOOP_URL to be used, got %q", baseURL)
	}
}

func TestResolveConfiguredAPIURLUsesDedicatedAPIEnvVariable(t *testing.T) {
	tempHome := t.TempDir()
	t.Setenv("HOME", tempHome)
	t.Setenv("PRELOOP_URL", "https://gateway.preloop.ai")
	t.Setenv("PRELOOP_API_URL", "https://api.preloop.ai")

	originalFlagURL := FlagURL
	originalFlagAPIURL := FlagAPIURL
	originalFlagToken := FlagToken
	FlagURL = ""
	FlagAPIURL = ""
	FlagToken = ""
	t.Cleanup(func() {
		FlagURL = originalFlagURL
		FlagAPIURL = originalFlagAPIURL
		FlagToken = originalFlagToken
	})

	baseURL, err := resolveConfiguredAPIURL()
	if err != nil {
		t.Fatalf("resolveConfiguredAPIURL returned error: %v", err)
	}
	if baseURL != "https://api.preloop.ai" {
		t.Fatalf("expected PRELOOP_API_URL to be used, got %q", baseURL)
	}

	publicURL, err := resolveConfiguredPublicURL()
	if err != nil {
		t.Fatalf("resolveConfiguredPublicURL returned error: %v", err)
	}
	if publicURL != "https://gateway.preloop.ai" {
		t.Fatalf("expected PRELOOP_URL to remain the public URL, got %q", publicURL)
	}
}

func TestShouldUseHeadlessOAuthDetectsSSH(t *testing.T) {
	restore := snapshotLoginFlags()
	defer restore()

	t.Setenv("SSH_CONNECTION", "client host 123 22")

	if !shouldUseHeadlessOAuth() {
		t.Fatal("expected SSH sessions to use headless OAuth")
	}
}

func TestShouldUseHeadlessOAuthHonorsLoopbackFlag(t *testing.T) {
	restore := snapshotLoginFlags()
	defer restore()

	t.Setenv("SSH_CONNECTION", "client host 123 22")
	loginLoopback = true

	if shouldUseHeadlessOAuth() {
		t.Fatal("expected --loopback to override SSH headless detection")
	}
}

func TestRootIncludesLoginAlias(t *testing.T) {
	for _, command := range rootCmd.Commands() {
		if command.Name() == "login" {
			return
		}
	}

	t.Fatal("expected root command to include a login alias")
}

func snapshotLoginFlags() func() {
	originalLoginToken := loginToken
	originalLoginHeadless := loginHeadless
	originalLoginLoopback := loginLoopback
	originalLoginCode := loginCode
	originalFlagAPIURL := FlagAPIURL

	return func() {
		loginToken = originalLoginToken
		loginHeadless = originalLoginHeadless
		loginLoopback = originalLoginLoopback
		loginCode = originalLoginCode
		FlagAPIURL = originalFlagAPIURL
	}
}

func TestMain(m *testing.M) {
	// Prevent tests from reading the developer's real config.
	originalHome := os.Getenv("HOME")
	tempHome, err := os.MkdirTemp("", "preloop-cli-tests-*")
	if err != nil {
		panic(err)
	}
	_ = os.Setenv("HOME", tempHome)

	code := m.Run()

	if originalHome == "" {
		_ = os.Unsetenv("HOME")
	} else {
		_ = os.Setenv("HOME", originalHome)
	}
	_ = os.RemoveAll(tempHome)
	os.Exit(code)
}
