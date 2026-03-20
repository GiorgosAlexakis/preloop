package api

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"

	"github.com/preloop/preloop/cli/internal/config"
)

func TestNewClientWithToken(t *testing.T) {
	client := NewClientWithToken("https://example.com", "test-token")

	if client.baseURL != "https://example.com" {
		t.Errorf("expected baseURL 'https://example.com', got '%s'", client.baseURL)
	}
	if client.token != "test-token" {
		t.Errorf("expected token 'test-token', got '%s'", client.token)
	}
	if !client.IsAuthenticated() {
		t.Error("expected IsAuthenticated() to return true")
	}
}

func TestNewClientWithToken_DefaultBaseURL(t *testing.T) {
	client := NewClientWithToken("", "tok")
	if client.baseURL != DefaultBaseURL {
		t.Errorf("expected default baseURL '%s', got '%s'", DefaultBaseURL, client.baseURL)
	}
}

func TestIsAuthenticated_NoToken(t *testing.T) {
	client := NewClientWithToken("https://example.com", "")
	if client.IsAuthenticated() {
		t.Error("expected IsAuthenticated() to return false for empty token")
	}
}

func TestSetToken(t *testing.T) {
	client := NewClientWithToken("https://example.com", "")
	if client.IsAuthenticated() {
		t.Fatal("should not be authenticated initially")
	}

	client.SetToken("new-token")
	if !client.IsAuthenticated() {
		t.Error("expected IsAuthenticated() to return true after SetToken")
	}
	if client.token != "new-token" {
		t.Errorf("expected token 'new-token', got '%s'", client.token)
	}
}

func TestBaseURL(t *testing.T) {
	client := NewClientWithToken("https://custom.api.com", "tok")
	if client.BaseURL() != "https://custom.api.com" {
		t.Errorf("expected BaseURL() 'https://custom.api.com', got '%s'", client.BaseURL())
	}
}

func TestGet_Success(t *testing.T) {
	expected := map[string]string{"status": "ok"}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			t.Errorf("expected GET, got %s", r.Method)
		}
		if r.Header.Get("Authorization") != "Bearer test-token" {
			t.Errorf("expected Bearer token, got '%s'", r.Header.Get("Authorization"))
		}
		if r.URL.Path != "/api/v1/test" {
			t.Errorf("expected path /api/v1/test, got %s", r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(expected)
	}))
	defer server.Close()

	client := NewClientWithToken(server.URL, "test-token")
	var result map[string]string
	if err := client.Get("/api/v1/test", &result); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result["status"] != "ok" {
		t.Errorf("expected status 'ok', got '%s'", result["status"])
	}
}

func TestPost_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("expected POST, got %s", r.Method)
		}
		if r.Header.Get("Content-Type") != "application/json" {
			t.Errorf("expected Content-Type application/json, got '%s'", r.Header.Get("Content-Type"))
		}

		var body map[string]string
		json.NewDecoder(r.Body).Decode(&body)
		if body["name"] != "test" {
			t.Errorf("expected body name 'test', got '%s'", body["name"])
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"id": "123"})
	}))
	defer server.Close()

	client := NewClientWithToken(server.URL, "tok")
	var result map[string]string
	err := client.Post("/test", map[string]string{"name": "test"}, &result)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result["id"] != "123" {
		t.Errorf("expected id '123', got '%s'", result["id"])
	}
}

func TestPostMultipart_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("expected POST, got %s", r.Method)
		}

		if err := r.ParseMultipartForm(1024 * 1024); err != nil {
			t.Fatalf("failed to parse multipart request: %v", err)
		}

		if got := r.FormValue("dry_run"); got != "true" {
			t.Errorf("expected dry_run=true, got %q", got)
		}

		file, header, err := r.FormFile("file")
		if err != nil {
			t.Fatalf("expected multipart file field: %v", err)
		}
		defer file.Close()

		content, err := io.ReadAll(file)
		if err != nil {
			t.Fatalf("failed reading multipart file: %v", err)
		}

		if header.Filename != "policy.yaml" {
			t.Errorf("expected filename policy.yaml, got %q", header.Filename)
		}
		if string(content) != "version: \"1.0\"\n" {
			t.Errorf("unexpected file content: %q", string(content))
		}

		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]bool{"ok": true})
	}))
	defer server.Close()

	client := NewClientWithToken(server.URL, "tok")
	var result map[string]bool
	err := client.PostMultipart(
		"/upload",
		map[string]string{"dry_run": "true"},
		"file",
		"policy.yaml",
		[]byte("version: \"1.0\"\n"),
		&result,
	)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !result["ok"] {
		t.Error("expected ok to be true")
	}
}

func TestGet_APIError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		w.Write([]byte(`{"detail":"Not authenticated"}`))
	}))
	defer server.Close()

	client := NewClientWithToken(server.URL, "bad-token")
	var result map[string]string
	err := client.Get("/test", &result)
	if err == nil {
		t.Fatal("expected error for 401 response")
	}
}

func TestClientRefreshesExpiredAccessTokenFromStoredConfig(t *testing.T) {
	tmpDir := t.TempDir()
	origHome := os.Getenv("HOME")
	os.Setenv("HOME", tmpDir)
	defer os.Setenv("HOME", origHome)

	requestCount := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/v1/test":
			requestCount++
			if requestCount == 1 {
				if r.Header.Get("Authorization") != "Bearer expired-token" {
					t.Fatalf("expected expired token on first request, got %q", r.Header.Get("Authorization"))
				}
				w.WriteHeader(http.StatusUnauthorized)
				_, _ = w.Write([]byte(`{"detail":"expired"}`))
				return
			}
			if r.Header.Get("Authorization") != "Bearer refreshed-token" {
				t.Fatalf("expected refreshed token on retry, got %q", r.Header.Get("Authorization"))
			}
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
		case "/oauth/token":
			if err := r.ParseForm(); err != nil {
				t.Fatalf("failed to parse token refresh request: %v", err)
			}
			if r.Form.Get("grant_type") != "refresh_token" {
				t.Fatalf("expected refresh_token grant, got %q", r.Form.Get("grant_type"))
			}
			if r.Form.Get("refresh_token") != "refresh-token" {
				t.Fatalf("expected stored refresh token, got %q", r.Form.Get("refresh_token"))
			}
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(map[string]string{
				"access_token":  "refreshed-token",
				"refresh_token": "rotated-refresh-token",
				"token_type":    "bearer",
			})
		default:
			t.Fatalf("unexpected request path %s", r.URL.Path)
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

	client, err := NewClient("", "")
	if err != nil {
		t.Fatalf("failed to build client: %v", err)
	}

	var result map[string]string
	if err := client.Get("/api/v1/test", &result); err != nil {
		t.Fatalf("expected refresh+retry to succeed, got %v", err)
	}
	if result["status"] != "ok" {
		t.Fatalf("expected ok response, got %#v", result)
	}
	if client.Token() != "refreshed-token" {
		t.Fatalf("expected in-memory access token to refresh, got %q", client.Token())
	}

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("failed to reload config: %v", err)
	}
	if cfg.AccessToken != "refreshed-token" {
		t.Fatalf("expected refreshed access token in config, got %q", cfg.AccessToken)
	}
	if cfg.RefreshToken != "rotated-refresh-token" {
		t.Fatalf("expected rotated refresh token in config, got %q", cfg.RefreshToken)
	}
}

func TestClientDoesNotRefreshWhenExplicitTokenOverrideIsUsed(t *testing.T) {
	tmpDir := t.TempDir()
	origHome := os.Getenv("HOME")
	os.Setenv("HOME", tmpDir)
	defer os.Setenv("HOME", origHome)

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/v1/test":
			w.WriteHeader(http.StatusUnauthorized)
			_, _ = w.Write([]byte(`{"detail":"unauthorized"}`))
		case "/oauth/token":
			t.Fatal("did not expect token refresh for explicit token override")
		default:
			t.Fatalf("unexpected request path %s", r.URL.Path)
		}
	}))
	defer server.Close()

	if err := config.Save(&config.Config{
		AccessToken:  "stale-config-token",
		RefreshToken: "refresh-token",
		APIURL:       server.URL,
	}); err != nil {
		t.Fatalf("failed to save config: %v", err)
	}

	client, err := NewClient("override-token", server.URL)
	if err != nil {
		t.Fatalf("failed to build client: %v", err)
	}

	var result map[string]string
	if err := client.Get("/api/v1/test", &result); err == nil {
		t.Fatal("expected 401 error when using explicit override token")
	}
}

func TestPut_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPut {
			t.Errorf("expected PUT, got %s", r.Method)
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]bool{"ok": true})
	}))
	defer server.Close()

	client := NewClientWithToken(server.URL, "tok")
	var result map[string]bool
	err := client.Put("/test", map[string]string{"key": "val"}, &result)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !result["ok"] {
		t.Error("expected ok to be true")
	}
}

func TestDelete_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodDelete {
			t.Errorf("expected DELETE, got %s", r.Method)
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"message": "deleted"})
	}))
	defer server.Close()

	client := NewClientWithToken(server.URL, "tok")
	var result map[string]string
	err := client.Delete("/test", &result)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result["message"] != "deleted" {
		t.Errorf("expected message 'deleted', got '%s'", result["message"])
	}
}

func TestGet_NoAuth(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "" {
			t.Errorf("expected no Authorization header, got '%s'", r.Header.Get("Authorization"))
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"public": "data"})
	}))
	defer server.Close()

	client := NewClientWithToken(server.URL, "")
	var result map[string]string
	err := client.Get("/public", &result)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}
