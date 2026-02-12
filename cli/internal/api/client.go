// Package api provides the HTTP client for interacting with the Preloop API.
package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/preloop/preloop/cli/internal/config"
)

const (
	// DefaultBaseURL is the default Preloop API endpoint.
	DefaultBaseURL = "http://localhost:8000"

	// DefaultTimeout is the default HTTP client timeout.
	DefaultTimeout = 30 * time.Second
)

// Client is an HTTP client for the Preloop API.
type Client struct {
	baseURL    string
	httpClient *http.Client
	token      string
}

// NewClient creates a new Preloop API client.
// tokenOverride and urlOverride allow CLI flags to take precedence over
// environment variables and the config file.
func NewClient(tokenOverride, urlOverride string) (*Client, error) {
	cfg, err := config.Resolve(tokenOverride, urlOverride)
	if err != nil {
		return nil, fmt.Errorf("failed to load config: %w", err)
	}

	return &Client{
		baseURL: cfg.APIURL,
		httpClient: &http.Client{
			Timeout: DefaultTimeout,
		},
		token: cfg.AccessToken,
	}, nil
}

// NewClientWithToken creates a new client with a specific token (useful for testing).
func NewClientWithToken(baseURL, token string) *Client {
	if baseURL == "" {
		baseURL = DefaultBaseURL
	}

	return &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: DefaultTimeout,
		},
		token: token,
	}
}

// Get performs a GET request to the specified path.
func (c *Client) Get(path string, result interface{}) error {
	return c.do(http.MethodGet, path, nil, result)
}

// Post performs a POST request to the specified path with the given body.
func (c *Client) Post(path string, body, result interface{}) error {
	return c.do(http.MethodPost, path, body, result)
}

// Put performs a PUT request to the specified path with the given body.
func (c *Client) Put(path string, body, result interface{}) error {
	return c.do(http.MethodPut, path, body, result)
}

// Delete performs a DELETE request to the specified path.
func (c *Client) Delete(path string, result interface{}) error {
	return c.do(http.MethodDelete, path, nil, result)
}

// do performs an HTTP request and decodes the response.
func (c *Client) do(method, path string, body, result interface{}) error {
	url := c.baseURL + path

	var bodyReader io.Reader
	if body != nil {
		jsonBody, err := json.Marshal(body)
		if err != nil {
			return fmt.Errorf("failed to marshal request body: %w", err)
		}
		bodyReader = bytes.NewReader(jsonBody)
	}

	req, err := http.NewRequest(method, url, bodyReader)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	if c.token != "" {
		req.Header.Set("Authorization", "Bearer "+c.token)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("API error (status %d): %s", resp.StatusCode, string(bodyBytes))
	}

	if result != nil {
		if err := json.NewDecoder(resp.Body).Decode(result); err != nil {
			return fmt.Errorf("failed to decode response: %w", err)
		}
	}

	return nil
}

// IsAuthenticated returns true if the client has a token configured.
func (c *Client) IsAuthenticated() bool {
	return c.token != ""
}

// SetToken updates the client's authentication token.
func (c *Client) SetToken(token string) {
	c.token = token
}

// BaseURL returns the configured base URL.
func (c *Client) BaseURL() string {
	return c.baseURL
}
