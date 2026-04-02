package mcpclient

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestClientStoresSessionIDAndListsTools(t *testing.T) {
	t.Parallel()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/mcp/v1" {
			t.Fatalf("unexpected path: %s", r.URL.Path)
		}

		body, err := io.ReadAll(r.Body)
		if err != nil {
			t.Fatalf("failed to read request body: %v", err)
		}

		var request jsonRPCRequest
		if err := json.Unmarshal(body, &request); err != nil {
			t.Fatalf("failed to decode request: %v", err)
		}

		switch request.Method {
		case "initialize":
			w.Header().Set(sessionHeaderName, "session-123")
			w.Header().Set("Content-Type", jsonContentType)
			_, _ = w.Write([]byte(`{
				"jsonrpc":"2.0",
				"id":2,
				"result":{
					"protocolVersion":"2024-11-05",
					"capabilities":{},
					"serverInfo":{"name":"preloop","version":"test"}
				}
			}`))
		case "notifications/initialized":
			if got := r.Header.Get(sessionHeaderName); got != "session-123" {
				t.Fatalf("expected session header on notification, got %q", got)
			}
			w.WriteHeader(http.StatusNoContent)
		case "tools/list":
			if got := r.Header.Get(sessionHeaderName); got != "session-123" {
				t.Fatalf("expected session header on tools/list, got %q", got)
			}
			w.Header().Set("Content-Type", jsonContentType)
			_, _ = w.Write([]byte(`{
				"jsonrpc":"2.0",
				"id":3,
				"result":{
					"tools":[
						{
							"name":"github.search",
							"description":"Search GitHub",
							"inputSchema":{
								"type":"object",
								"properties":{"query":{"type":"string"}},
								"required":["query"]
							}
						}
					]
				}
			}`))
		default:
			t.Fatalf("unexpected method: %s", request.Method)
		}
	}))
	defer server.Close()

	client := New(server.URL, "token", time.Second, nil)

	if err := client.Initialize(context.Background(), "preloop-cli", "test"); err != nil {
		t.Fatalf("initialize failed: %v", err)
	}

	tools, err := client.ListTools(context.Background())
	if err != nil {
		t.Fatalf("list tools failed: %v", err)
	}

	if len(tools) != 1 {
		t.Fatalf("expected 1 tool, got %d", len(tools))
	}
	if tools[0].Name != "github.search" {
		t.Fatalf("unexpected tool name: %s", tools[0].Name)
	}
}

func TestClientCallToolDecodesSSEResponse(t *testing.T) {
	t.Parallel()

	var progress bytes.Buffer

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, err := io.ReadAll(r.Body)
		if err != nil {
			t.Fatalf("failed to read request body: %v", err)
		}

		var request jsonRPCRequest
		if err := json.Unmarshal(body, &request); err != nil {
			t.Fatalf("failed to decode request: %v", err)
		}

		switch request.Method {
		case "initialize":
			w.Header().Set(sessionHeaderName, "session-456")
			w.Header().Set("Content-Type", jsonContentType)
			_, _ = w.Write([]byte(`{"jsonrpc":"2.0","id":2,"result":{"protocolVersion":"2024-11-05","capabilities":{},"serverInfo":{"name":"preloop","version":"test"}}}`))
		case "notifications/initialized":
			w.WriteHeader(http.StatusNoContent)
		case "tools/call":
			if got := r.Header.Get(sessionHeaderName); got != "session-456" {
				t.Fatalf("expected session header on tools/call, got %q", got)
			}
			w.Header().Set("Content-Type", sseContentType)
			_, _ = w.Write([]byte(
				"data: {\"jsonrpc\":\"2.0\",\"method\":\"notifications/progress\",\"params\":{\"message\":\"waiting for approval\"}}\n\n" +
					"data: {\"jsonrpc\":\"2.0\",\"id\":3,\"result\":{\"content\":[{\"type\":\"text\",\"text\":\"done\"}],\"structuredContent\":{\"ok\":true}}}\n\n",
			))
		default:
			t.Fatalf("unexpected method: %s", request.Method)
		}
	}))
	defer server.Close()

	client := New(server.URL, "token", time.Second, &progress)

	if err := client.Initialize(context.Background(), "preloop-cli", "test"); err != nil {
		t.Fatalf("initialize failed: %v", err)
	}

	result, err := client.CallTool(context.Background(), "github.search", map[string]any{
		"query": "preloop",
	})
	if err != nil {
		t.Fatalf("call tool failed: %v", err)
	}

	if progress.String() != "waiting for approval\n" {
		t.Fatalf("unexpected progress output: %q", progress.String())
	}
	if len(result.Content) != 1 {
		t.Fatalf("expected 1 content item, got %d", len(result.Content))
	}
	if text, _ := result.Content[0]["text"].(string); text != "done" {
		t.Fatalf("unexpected text output: %q", text)
	}

	structured, ok := result.StructuredContent.(map[string]any)
	if !ok {
		t.Fatalf("expected structured content map, got %T", result.StructuredContent)
	}
	if okValue, _ := structured["ok"].(bool); !okValue {
		t.Fatalf("expected structured content ok=true, got %#v", structured)
	}
}
