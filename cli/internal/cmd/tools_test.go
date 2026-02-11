package cmd

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/preloop/preloop/cli/internal/api"
)

func TestFindToolByName_ExactMatch(t *testing.T) {
	tools := []Tool{
		{ID: "id-1", Name: "get_issue"},
		{ID: "id-2", Name: "create_issue"},
	}

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(tools)
	}))
	defer server.Close()

	client := api.NewClientWithToken(server.URL, "tok")
	id, err := findToolByName(client, "get_issue")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if id != "id-1" {
		t.Errorf("expected 'id-1', got '%s'", id)
	}
}

func TestFindToolByName_ByID(t *testing.T) {
	tools := []Tool{
		{ID: "id-1", Name: "get_issue"},
	}

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(tools)
	}))
	defer server.Close()

	client := api.NewClientWithToken(server.URL, "tok")
	id, err := findToolByName(client, "id-1")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if id != "id-1" {
		t.Errorf("expected 'id-1', got '%s'", id)
	}
}

func TestFindToolByName_CaseInsensitive(t *testing.T) {
	tools := []Tool{
		{ID: "id-1", Name: "Get_Issue"},
	}

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(tools)
	}))
	defer server.Close()

	client := api.NewClientWithToken(server.URL, "tok")
	id, err := findToolByName(client, "get_issue")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if id != "id-1" {
		t.Errorf("expected 'id-1', got '%s'", id)
	}
}

func TestFindToolByName_NotFound(t *testing.T) {
	tools := []Tool{
		{ID: "id-1", Name: "get_issue"},
	}

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(tools)
	}))
	defer server.Close()

	client := api.NewClientWithToken(server.URL, "tok")
	_, err := findToolByName(client, "nonexistent")
	if err == nil {
		t.Fatal("expected error for nonexistent tool")
	}
}

func TestToolsListCmd_JSONOutput(t *testing.T) {
	tools := []Tool{
		{ID: "1", Name: "get_issue", Enabled: true, Category: "tracker", RiskLevel: "low", Description: "Get an issue"},
		{ID: "2", Name: "shell_exec", Enabled: false, Category: "system", RiskLevel: "high", Description: "Execute shell command"},
	}

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(tools)
	}))
	defer server.Close()

	client := api.NewClientWithToken(server.URL, "tok")

	// Test filtering: enabled only
	var allTools []Tool
	if err := client.Get(toolsListPath, &allTools); err != nil {
		t.Fatalf("failed to get tools: %v", err)
	}

	var enabled []Tool
	for _, tool := range allTools {
		if tool.Enabled {
			enabled = append(enabled, tool)
		}
	}
	if len(enabled) != 1 {
		t.Errorf("expected 1 enabled tool, got %d", len(enabled))
	}
	if enabled[0].Name != "get_issue" {
		t.Errorf("expected enabled tool 'get_issue', got '%s'", enabled[0].Name)
	}

	// Test filtering: by category
	var system []Tool
	for _, tool := range allTools {
		if tool.Category == "system" {
			system = append(system, tool)
		}
	}
	if len(system) != 1 {
		t.Errorf("expected 1 system tool, got %d", len(system))
	}
}

func TestToolJSON_Marshaling(t *testing.T) {
	tool := Tool{
		ID:          "abc-123",
		Name:        "test_tool",
		Description: "A test tool",
		Enabled:     true,
		Category:    "testing",
		RiskLevel:   "low",
		Permissions: []string{"read", "write"},
	}

	data, err := json.Marshal(tool)
	if err != nil {
		t.Fatalf("failed to marshal: %v", err)
	}

	var parsed Tool
	if err := json.Unmarshal(data, &parsed); err != nil {
		t.Fatalf("failed to unmarshal: %v", err)
	}

	if parsed.ID != tool.ID || parsed.Name != tool.Name || parsed.Enabled != tool.Enabled {
		t.Error("round-trip JSON marshaling failed")
	}
	if len(parsed.Permissions) != 2 {
		t.Errorf("expected 2 permissions, got %d", len(parsed.Permissions))
	}
}
