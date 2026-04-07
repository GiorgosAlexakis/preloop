package cmd

import (
	"bytes"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	"github.com/preloop/preloop/cli/internal/config"
)

func TestResolveConfiguredAPIURLUsesEnvVariable(t *testing.T) {
	tempHome := t.TempDir()
	t.Setenv("HOME", tempHome)
	t.Setenv("PRELOOP_URL", "http://example.test/api/")

	originalFlagURL := FlagURL
	originalFlagToken := FlagToken
	FlagURL = ""
	FlagToken = ""
	t.Cleanup(func() {
		FlagURL = originalFlagURL
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

func TestRunAuthStatusRefreshesStoredLoginBeforeFetchingUser(t *testing.T) {
	tempHome := t.TempDir()
	t.Setenv("HOME", tempHome)

	restore := snapshotLoginFlags()
	defer restore()

	requestedUserInfo := false
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/oauth/token":
			if err := r.ParseForm(); err != nil {
				t.Fatalf("failed to parse refresh form: %v", err)
			}
			if r.Form.Get("grant_type") != "refresh_token" {
				t.Fatalf("expected refresh_token grant, got %q", r.Form.Get("grant_type"))
			}
			if r.Form.Get("refresh_token") != "refresh-token" {
				t.Fatalf("expected stored refresh token, got %q", r.Form.Get("refresh_token"))
			}
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"access_token":"fresh-token","refresh_token":"rotated-refresh"}`))
		case userInfoPath:
			requestedUserInfo = true
			if got := r.Header.Get("Authorization"); got != "Bearer fresh-token" {
				t.Fatalf("expected refreshed bearer token, got %q", got)
			}
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"id":"u1","email":"user@example.com","name":"Test User","organization":"Acme"}`))
		default:
			t.Fatalf("unexpected path %q", r.URL.Path)
		}
	}))
	defer server.Close()

	if err := config.Save(&config.Config{
		AccessToken:  "expired-token",
		RefreshToken: "refresh-token",
		APIURL:       server.URL,
	}); err != nil {
		t.Fatalf("failed to save config: %v", err)
	}

	output := captureStdout(t, func() error {
		return runAuthStatus(authStatusCmd, nil)
	})

	if !requestedUserInfo {
		t.Fatal("expected auth status to fetch user info after refresh")
	}
	if !strings.Contains(output, "Authenticated") || !strings.Contains(output, "Test User") {
		t.Fatalf("expected authenticated output after refresh, got %q", output)
	}
}

func TestRunAuthStatusPrintsUnderlyingError(t *testing.T) {
	tempHome := t.TempDir()
	t.Setenv("HOME", tempHome)

	restore := snapshotLoginFlags()
	defer restore()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != userInfoPath {
			t.Fatalf("unexpected path %q", r.URL.Path)
		}
		w.WriteHeader(http.StatusBadGateway)
		_, _ = w.Write([]byte(`{"detail":"upstream unavailable"}`))
	}))
	defer server.Close()

	if err := config.Save(&config.Config{
		AccessToken: "access-token",
		APIURL:      server.URL,
	}); err != nil {
		t.Fatalf("failed to save config: %v", err)
	}

	output := captureStdout(t, func() error {
		return runAuthStatus(authStatusCmd, nil)
	})

	if !strings.Contains(output, "upstream unavailable") {
		t.Fatalf("expected auth status to print underlying error, got %q", output)
	}
}

func snapshotLoginFlags() func() {
	originalLoginToken := loginToken
	originalLoginHeadless := loginHeadless
	originalLoginLoopback := loginLoopback
	originalLoginCode := loginCode

	return func() {
		loginToken = originalLoginToken
		loginHeadless = originalLoginHeadless
		loginLoopback = originalLoginLoopback
		loginCode = originalLoginCode
	}
}

func captureStdout(t *testing.T, fn func() error) string {
	t.Helper()

	oldStdout := os.Stdout
	readPipe, writePipe, err := os.Pipe()
	if err != nil {
		t.Fatalf("failed to create stdout pipe: %v", err)
	}
	os.Stdout = writePipe
	defer func() {
		os.Stdout = oldStdout
	}()

	runErr := fn()
	_ = writePipe.Close()
	if runErr != nil {
		t.Fatalf("unexpected error: %v", runErr)
	}

	var output bytes.Buffer
	if _, err := io.Copy(&output, readPipe); err != nil {
		t.Fatalf("failed to read stdout: %v", err)
	}
	return output.String()
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
