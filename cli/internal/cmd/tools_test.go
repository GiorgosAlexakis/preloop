package cmd

import (
	"strings"
	"testing"

	"github.com/preloop/preloop/cli/internal/mcpclient"
)

func TestFindToolByName_ExactMatch(t *testing.T) {
	tools := []mcpclient.Tool{
		{Name: "github.search"},
		{Name: "shell"},
	}

	tool, err := findToolByName(tools, "github.search")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if tool.Name != "github.search" {
		t.Fatalf("expected github.search, got %q", tool.Name)
	}
}

func TestFindToolByName_CaseInsensitive(t *testing.T) {
	tools := []mcpclient.Tool{
		{Name: "GitHub.Search"},
	}

	tool, err := findToolByName(tools, "github.search")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if tool.Name != "GitHub.Search" {
		t.Fatalf("expected GitHub.Search, got %q", tool.Name)
	}
}

func TestFindToolByName_NotFound(t *testing.T) {
	tools := []mcpclient.Tool{
		{Name: "github.search"},
	}

	_, err := findToolByName(tools, "nonexistent")
	if err == nil {
		t.Fatal("expected error for nonexistent tool")
	}
	if !strings.Contains(err.Error(), "Available tools: github.search") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestDecodeToolArguments_JSONObject(t *testing.T) {
	arguments, err := decodeToolArguments([]byte(`{"query":"preloop","limit":5}`))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if query, _ := arguments["query"].(string); query != "preloop" {
		t.Fatalf("unexpected query: %#v", arguments)
	}
	if limit, _ := arguments["limit"].(float64); limit != 5 {
		t.Fatalf("unexpected limit: %#v", arguments)
	}
}

func TestDecodeToolArguments_RejectsArrays(t *testing.T) {
	_, err := decodeToolArguments([]byte(`["not","an","object"]`))
	if err == nil {
		t.Fatal("expected an error for non-object arguments")
	}
}

func TestSchemaFields(t *testing.T) {
	required, optional := schemaFields(map[string]any{
		"properties": map[string]any{
			"limit": map[string]any{"type": "number"},
			"query": map[string]any{"type": "string"},
			"sort":  map[string]any{"type": "string"},
		},
		"required": []any{"query"},
	})

	if strings.Join(required, ",") != "query" {
		t.Fatalf("unexpected required fields: %v", required)
	}
	if strings.Join(optional, ",") != "limit,sort" {
		t.Fatalf("unexpected optional fields: %v", optional)
	}
}
