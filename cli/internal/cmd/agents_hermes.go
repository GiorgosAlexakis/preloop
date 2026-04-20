package cmd

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"gopkg.in/yaml.v3"
)

// hermesAgentName is the canonical product name used in agentSpecs and CLI output.
const hermesAgentName = "Hermes"

// hermesSourceType is the stable runtime/API kind string emitted by the CLI and
// recognised by the backend allowlist (RUNTIME_SESSION_SOURCE_TYPES).
const hermesSourceType = "hermes"

// hermesConfigRelativePaths lists the YAML config files Hermes Agent reads at
// startup. Hermes documents `~/.hermes/config.yaml` as the canonical path; the
// `.yml` variant is included to cover users who follow common YAML conventions.
var hermesConfigRelativePaths = []string{
	".hermes/config.yaml",
	".hermes/config.yml",
}

// hermesDetectionPaths lets us recognise an installed-but-unconfigured Hermes
// agent so `preloop agents discover` can still synthesize an enrollment plan.
var hermesDetectionPaths = []string{
	".hermes",
	".hermes/hermes-agent",
	".hermes/sessions",
	".local/bin/hermes",
}

// hermesBootstrapConfigPath is where Preloop will create a managed Hermes
// config when none exists locally yet.
const hermesBootstrapConfigPath = ".hermes/config.yaml"

// isHermesAgent reports whether the given agent is the Hermes managed agent.
// It accepts the human-readable display name ("Hermes") and the source type.
func isHermesAgent(agent AgentConfig) bool {
	name := strings.ToLower(strings.TrimSpace(agent.Name))
	return name == strings.ToLower(hermesAgentName) || name == hermesSourceType
}

// parseHermesConfig loads a Hermes Agent YAML config and extracts its declared
// MCP servers. Hermes uses an `mcp_servers:` mapping with stdio entries
// (`command`/`args`/`env`) and HTTP entries (`url`/`headers`).
func parseHermesConfig(path string) (map[string]MCPDef, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	doc, err := decodeHermesYAMLDocument(data)
	if err != nil {
		return nil, err
	}
	return parseServerMapFromDocument(doc), nil
}

// loadHermesAgentConfigDocument reads the Hermes YAML config, returning an
// empty map when the config file does not yet exist so we can synthesize one
// during onboarding.
func loadHermesAgentConfigDocument(path string) (map[string]interface{}, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return map[string]interface{}{}, nil
		}
		return nil, err
	}
	if len(strings.TrimSpace(string(data))) == 0 {
		return map[string]interface{}{}, nil
	}
	return decodeHermesYAMLDocument(data)
}

// writeHermesAgentConfigDocument serializes a Hermes managed config back to
// disk as YAML, preserving the directory permissions used by the rest of the
// agent enrollment pipeline.
func writeHermesAgentConfigDocument(path string, doc map[string]interface{}) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return fmt.Errorf("failed to create config directory: %w", err)
	}
	normalised := normaliseForYAMLEncoding(doc)
	data, err := yaml.Marshal(normalised)
	if err != nil {
		return fmt.Errorf("failed to encode managed Hermes config: %w", err)
	}
	if len(data) == 0 || data[len(data)-1] != '\n' {
		data = append(data, '\n')
	}
	if err := os.WriteFile(path, data, 0644); err != nil {
		return fmt.Errorf("failed to write managed Hermes config: %w", err)
	}
	return nil
}

// decodeHermesYAMLDocument parses YAML bytes into a generic JSON-compatible
// map[string]interface{} document. The yaml.v3 decoder yields
// map[interface{}]interface{} for nested objects by default, which breaks the
// rest of the agent pipeline (which assumes JSON-style maps); this helper
// normalises the shape.
func decodeHermesYAMLDocument(data []byte) (map[string]interface{}, error) {
	var raw interface{}
	if err := yaml.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("failed to parse Hermes YAML config: %w", err)
	}
	if raw == nil {
		return map[string]interface{}{}, nil
	}
	normalised, ok := normaliseFromYAMLDecoding(raw).(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("Hermes config root must be a YAML mapping, got %T", raw)
	}
	return normalised, nil
}

// normaliseFromYAMLDecoding converts the loosely typed values returned by
// yaml.Unmarshal (e.g. map[interface{}]interface{}) into JSON-friendly
// map[string]interface{} / []interface{} that the rest of the agent pipeline
// understands. Non-string keys are coerced via fmt.Sprint.
func normaliseFromYAMLDecoding(value interface{}) interface{} {
	switch typed := value.(type) {
	case map[interface{}]interface{}:
		result := make(map[string]interface{}, len(typed))
		for key, child := range typed {
			result[fmt.Sprint(key)] = normaliseFromYAMLDecoding(child)
		}
		return result
	case map[string]interface{}:
		result := make(map[string]interface{}, len(typed))
		for key, child := range typed {
			result[key] = normaliseFromYAMLDecoding(child)
		}
		return result
	case []interface{}:
		result := make([]interface{}, len(typed))
		for index, child := range typed {
			result[index] = normaliseFromYAMLDecoding(child)
		}
		return result
	default:
		return typed
	}
}

// normaliseForYAMLEncoding makes sure values produced by JSON-style cloning
// (which can introduce json.Number or other interface mixes) round-trip cleanly
// through the YAML encoder. We re-marshal/unmarshal through encoding/json so
// the resulting structure is uniformly typed.
func normaliseForYAMLEncoding(doc map[string]interface{}) map[string]interface{} {
	bytes, err := json.Marshal(doc)
	if err != nil {
		return doc
	}
	var out map[string]interface{}
	if err := json.Unmarshal(bytes, &out); err != nil {
		return doc
	}
	return out
}

// hermesManagedMCPAdapter is the Hermes-specific override over the generic
// adapter. It guarantees the `mcp_servers` container shape that Hermes expects
// and emits a managed entry that uses Hermes' HTTP MCP server schema.
type hermesManagedMCPAdapter struct {
	agent AgentConfig
}

func (a hermesManagedMCPAdapter) Key() string {
	return hermesSourceType
}

// EnsureServerContainer returns the `mcp_servers` mapping from the document,
// creating it when missing. Hermes documents mcp servers under the snake_case
// key `mcp_servers:` (see https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp).
func (a hermesManagedMCPAdapter) EnsureServerContainer(doc map[string]interface{}) (map[string]interface{}, error) {
	if servers, ok := asObjectMap(doc["mcp_servers"]); ok {
		return servers, nil
	}
	created := make(map[string]interface{})
	doc["mcp_servers"] = created
	return created, nil
}

// BuildManagedServer returns the Hermes mcp_servers entry for Preloop. Hermes'
// HTTP MCP transport reads `url:` and a `headers:` mapping for bearer auth.
func (a hermesManagedMCPAdapter) BuildManagedServer(baseURL, token string) map[string]interface{} {
	return map[string]interface{}{
		"url": strings.TrimRight(baseURL, "/") + "/mcp/v1",
		"headers": map[string]interface{}{
			"Authorization": "Bearer " + token,
		},
		"enabled": true,
	}
}

// ValidateManagedConfig confirms the Preloop entry exists in `mcp_servers` and
// is correctly authorised.
func (a hermesManagedMCPAdapter) ValidateManagedConfig(doc map[string]interface{}, baseURL string) map[string]interface{} {
	expectedURL := strings.TrimRight(baseURL, "/") + "/mcp/v1"
	result := map[string]interface{}{
		"adapter_key":             a.Key(),
		"expected_preloop_url":    expectedURL,
		"preloop_server_present":  false,
		"preloop_url_ok":          false,
		"transport_ok":            true, // Hermes infers transport from url presence
		"authorization_header_ok": false,
		"validation_passed":       false,
	}
	servers, ok := asObjectMap(doc["mcp_servers"])
	if !ok {
		return result
	}
	preloop, ok := asObjectMap(servers["preloop"])
	if !ok {
		return result
	}
	result["preloop_server_present"] = true
	if url, _ := preloop["url"].(string); url == expectedURL {
		result["preloop_url_ok"] = true
	}
	if headers, ok := asObjectMap(preloop["headers"]); ok {
		if auth, _ := headers["Authorization"].(string); strings.HasPrefix(auth, "Bearer ") &&
			strings.TrimSpace(strings.TrimPrefix(auth, "Bearer ")) != "" {
			result["authorization_header_ok"] = true
		}
	}
	result["validation_passed"] =
		result["preloop_server_present"] == true &&
			result["preloop_url_ok"] == true &&
			result["transport_ok"] == true &&
			result["authorization_header_ok"] == true
	return result
}
