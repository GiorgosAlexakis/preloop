package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
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
