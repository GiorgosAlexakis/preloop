package cmd

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"net/url"
	"os/exec"
	"runtime"
	"time"

	"github.com/spf13/cobra"

	"github.com/preloop/preloop/cli/internal/api"
	"github.com/preloop/preloop/cli/internal/config"
)

const (
	// OAuth callback port for local server
	callbackPort = 8484

	// OAuth paths
	authorizePath = "/oauth/authorize"
	tokenPath     = "/oauth/token"
	userInfoPath  = "/api/v1/users/me"
)

// TokenResponse represents the OAuth token response.
type TokenResponse struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	ExpiresIn    int    `json:"expires_in"`
	TokenType    string `json:"token_type"`
}

// UserInfo represents the authenticated user's information.
type UserInfo struct {
	ID           string `json:"id"`
	Email        string `json:"email"`
	Name         string `json:"name"`
	Organization string `json:"organization"`
}

// authCmd represents the auth command group.
var authCmd = &cobra.Command{
	Use:   "auth",
	Short: "Manage authentication",
	Long:  `Manage authentication with your Preloop account.`,
}

// authLoginCmd represents the auth login command.
var authLoginCmd = &cobra.Command{
	Use:   "login",
	Short: "Authenticate with Preloop",
	Long: `Authenticate with your Preloop account.

With --token: saves the provided API token directly (no server required).
Without --token: opens a browser for OAuth authentication.

Examples:
  preloop auth login --token <your-token>
  preloop auth login --token <your-token> --url http://localhost:8000
  preloop auth login                          # OAuth browser flow`,
	RunE: runAuthLogin,
}

// authLogoutCmd represents the auth logout command.
var authLogoutCmd = &cobra.Command{
	Use:   "logout",
	Short: "Log out of Preloop",
	Long:  `Log out of your Preloop account and remove stored credentials.`,
	RunE:  runAuthLogout,
}

// authStatusCmd represents the auth status command.
var authStatusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show authentication status",
	Long:  `Show the current authentication status and logged-in user.`,
	RunE:  runAuthStatus,
}

// authTokenCmd represents the auth token command.
var authTokenCmd = &cobra.Command{
	Use:   "token",
	Short: "Print current access token",
	Long: `Print the current access token for use in scripts and automation.

This command outputs only the token with no additional formatting,
making it suitable for use in shell scripts or as input to other commands.

Examples:
  # Use token in a curl command
  curl -H "Authorization: Bearer $(preloop auth token)" http://localhost:8000/api/v1/users/me

  # Export as environment variable
  export PRELOOP_TOKEN=$(preloop auth token)`,
	RunE: runAuthToken,
}

var loginToken string

func init() {
	authCmd.AddCommand(authLoginCmd)
	authCmd.AddCommand(authLogoutCmd)
	authCmd.AddCommand(authStatusCmd)
	authCmd.AddCommand(authTokenCmd)

	authLoginCmd.Flags().StringVar(&loginToken, "token", "", "API access token (skip OAuth and save directly)")
}

// runAuthLogin handles both token-based and OAuth login.
// If --token is provided, it saves the token directly.
// Otherwise, it falls back to the OAuth browser flow.
func runAuthLogin(cmd *cobra.Command, args []string) error {
	token := loginToken

	// Also accept the global --token flag as a fallback
	if token == "" {
		token = FlagToken
	}

	if token != "" {
		return runTokenLogin(token)
	}

	// No token provided — fall back to OAuth browser flow
	return runOAuthLogin()
}

// runTokenLogin saves a token directly to the config file.
func runTokenLogin(token string) error {
	// Determine the API URL to persist (flag > current config > default)
	apiURL := FlagURL
	if apiURL == "" {
		cfg, err := config.Load()
		if err == nil && cfg.APIURL != "" {
			apiURL = cfg.APIURL
		} else {
			apiURL = config.DefaultAPIURL
		}
	}

	// Save token and URL to config
	if err := config.SetTokens(token, ""); err != nil {
		return fmt.Errorf("failed to save token: %w", err)
	}
	if err := config.SetAPIURL(apiURL); err != nil {
		return fmt.Errorf("failed to save API URL: %w", err)
	}

	// Verify the token by fetching user info
	client := api.NewClientWithToken(apiURL, token)
	var userInfo UserInfo
	if err := client.Get(userInfoPath, &userInfo); err != nil {
		fmt.Println("Token saved (could not verify — server may be unreachable)")
		fmt.Printf("  API URL: %s\n", apiURL)
		return nil
	}

	fmt.Println("Authenticated successfully!")
	fmt.Printf("  User:    %s (%s)\n", userInfo.Name, userInfo.Email)
	if userInfo.Organization != "" {
		fmt.Printf("  Org:     %s\n", userInfo.Organization)
	}
	fmt.Printf("  API URL: %s\n", apiURL)

	return nil
}

// runOAuthLogin implements the OAuth browser login flow.
func runOAuthLogin() error {
	// Load config to get API URL
	cfg, err := config.Load()
	if err != nil {
		return fmt.Errorf("failed to load config: %w", err)
	}

	baseURL := cfg.APIURL
	if baseURL == "" {
		baseURL = api.DefaultBaseURL
	}
	if FlagURL != "" {
		baseURL = FlagURL
	}

	// Generate state for CSRF protection
	state, err := generateState()
	if err != nil {
		return fmt.Errorf("failed to generate state: %w", err)
	}

	// Channel to receive the authorization code
	codeChan := make(chan string, 1)
	errChan := make(chan error, 1)

	// Start local HTTP server to receive the callback
	listener, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", callbackPort))
	if err != nil {
		return fmt.Errorf("failed to start callback server: %w", err)
	}

	server := &http.Server{
		Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			handleOAuthCallback(w, r, state, codeChan, errChan)
		}),
	}

	// Start server in background
	go func() {
		if err := server.Serve(listener); err != nil && err != http.ErrServerClosed {
			errChan <- fmt.Errorf("callback server error: %w", err)
		}
	}()

	// Build authorization URL
	redirectURI := fmt.Sprintf("http://localhost:%d/callback", callbackPort)
	authURL := fmt.Sprintf("%s%s?response_type=code&redirect_uri=%s&state=%s",
		baseURL,
		authorizePath,
		url.QueryEscape(redirectURI),
		url.QueryEscape(state),
	)

	fmt.Println("Opening browser for authentication...")
	fmt.Printf("If the browser doesn't open, please visit:\n%s\n\n", authURL)

	// Open browser
	if err := openBrowser(authURL); err != nil {
		fmt.Printf("Warning: Could not open browser: %v\n", err)
	}

	fmt.Println("Waiting for authentication...")

	// Wait for callback or timeout
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	var code string
	select {
	case code = <-codeChan:
		// Successfully received code
	case err := <-errChan:
		server.Shutdown(context.Background())
		return err
	case <-ctx.Done():
		server.Shutdown(context.Background())
		return fmt.Errorf("authentication timed out")
	}

	// Shutdown the callback server
	server.Shutdown(context.Background())

	// Exchange code for tokens
	fmt.Println("Exchanging code for tokens...")

	tokenResp, err := exchangeCodeForTokens(baseURL, code, redirectURI)
	if err != nil {
		return fmt.Errorf("failed to exchange code for tokens: %w", err)
	}

	// Save tokens to config
	if err := config.SetTokens(tokenResp.AccessToken, tokenResp.RefreshToken); err != nil {
		return fmt.Errorf("failed to save tokens: %w", err)
	}
	if err := config.SetAPIURL(baseURL); err != nil {
		return fmt.Errorf("failed to save API URL: %w", err)
	}

	// Fetch and display user info
	client := api.NewClientWithToken(baseURL, tokenResp.AccessToken)
	var userInfo UserInfo
	if err := client.Get(userInfoPath, &userInfo); err != nil {
		// Still successful login, just can't get user info
		fmt.Println("\nSuccessfully authenticated!")
		return nil
	}

	fmt.Println("\nSuccessfully authenticated!")
	fmt.Printf("Logged in as: %s (%s)\n", userInfo.Name, userInfo.Email)
	if userInfo.Organization != "" {
		fmt.Printf("Organization: %s\n", userInfo.Organization)
	}

	return nil
}

// runAuthLogout clears stored credentials.
func runAuthLogout(cmd *cobra.Command, args []string) error {
	if !config.IsAuthenticated() {
		fmt.Println("Not currently logged in")
		return nil
	}

	if err := config.Clear(); err != nil {
		return fmt.Errorf("failed to clear credentials: %w", err)
	}

	fmt.Println("Successfully logged out")
	return nil
}

// runAuthStatus shows the current authentication status.
func runAuthStatus(cmd *cobra.Command, args []string) error {
	cfg, err := config.Resolve(FlagToken, FlagURL)
	if err != nil {
		return fmt.Errorf("failed to load config: %w", err)
	}

	if cfg.AccessToken == "" {
		fmt.Println("Not authenticated")
		fmt.Println("Run 'preloop auth login --token <your-token>' to authenticate")
		return nil
	}

	// Create API client and fetch user info
	client, err := api.NewClient(FlagToken, FlagURL)
	if err != nil {
		return fmt.Errorf("failed to initialize API client: %w", err)
	}

	var userInfo UserInfo
	if err := client.Get(userInfoPath, &userInfo); err != nil {
		fmt.Println("Authenticated (token may be invalid or server unreachable)")
		fmt.Printf("  API URL: %s\n", cfg.APIURL)
		fmt.Println("Run 'preloop auth login --token <your-token>' to re-authenticate")
		return nil
	}

	fmt.Println("Authenticated")
	fmt.Printf("  User:    %s\n", userInfo.Name)
	fmt.Printf("  Email:   %s\n", userInfo.Email)
	if userInfo.Organization != "" {
		fmt.Printf("  Org:     %s\n", userInfo.Organization)
	}
	fmt.Printf("  API URL: %s\n", cfg.APIURL)

	return nil
}

// runAuthToken prints the current access token.
func runAuthToken(cmd *cobra.Command, args []string) error {
	cfg, err := config.Resolve(FlagToken, FlagURL)
	if err != nil {
		return fmt.Errorf("failed to load config: %w", err)
	}

	if cfg.AccessToken == "" {
		return fmt.Errorf("not authenticated - run 'preloop auth login --token <your-token>' first")
	}

	client, err := api.NewClient(FlagToken, FlagURL)
	if err != nil {
		return fmt.Errorf("failed to initialize API client: %w", err)
	}
	if FlagToken == "" && cfg.RefreshToken != "" {
		if err := client.RefreshAccessToken(); err != nil {
			return fmt.Errorf("stored login expired - run 'preloop auth login' again: %w", err)
		}
	}

	// Print just the token with no newline for scripting
	fmt.Print(client.Token())
	return nil
}

// handleOAuthCallback handles the OAuth callback from the browser.
func handleOAuthCallback(w http.ResponseWriter, r *http.Request, expectedState string, codeChan chan<- string, errChan chan<- error) {
	query := r.URL.Query()

	// Check for errors
	if errMsg := query.Get("error"); errMsg != "" {
		errDesc := query.Get("error_description")
		w.Header().Set("Content-Type", "text/html")
		w.WriteHeader(http.StatusBadRequest)
		fmt.Fprintf(w, "<html><body><h1>Authentication Failed</h1><p>%s: %s</p><p>You can close this window.</p></body></html>", errMsg, errDesc)
		errChan <- fmt.Errorf("OAuth error: %s - %s", errMsg, errDesc)
		return
	}

	// Verify state
	state := query.Get("state")
	if state != expectedState {
		w.Header().Set("Content-Type", "text/html")
		w.WriteHeader(http.StatusBadRequest)
		fmt.Fprintf(w, "<html><body><h1>Authentication Failed</h1><p>Invalid state parameter</p><p>You can close this window.</p></body></html>")
		errChan <- fmt.Errorf("invalid state parameter")
		return
	}

	// Get authorization code
	code := query.Get("code")
	if code == "" {
		w.Header().Set("Content-Type", "text/html")
		w.WriteHeader(http.StatusBadRequest)
		fmt.Fprintf(w, "<html><body><h1>Authentication Failed</h1><p>No authorization code received</p><p>You can close this window.</p></body></html>")
		errChan <- fmt.Errorf("no authorization code received")
		return
	}

	// Success
	w.Header().Set("Content-Type", "text/html")
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, `<html>
<head>
	<style>
		body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background: linear-gradient(135deg, #667eea 0%%, #764ba2 100%%); }
		.card { background: white; padding: 40px; border-radius: 16px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.2); }
		h1 { color: #333; margin-bottom: 10px; }
		p { color: #666; }
		.checkmark { font-size: 48px; margin-bottom: 20px; }
	</style>
</head>
<body>
	<div class="card">
		<div class="checkmark">✓</div>
		<h1>Authentication Successful</h1>
		<p>You can close this window and return to the terminal.</p>
	</div>
</body>
</html>`)

	codeChan <- code
}

// exchangeCodeForTokens exchanges the authorization code for access and refresh tokens.
func exchangeCodeForTokens(baseURL, code, redirectURI string) (*TokenResponse, error) {
	tokenURL := baseURL + tokenPath

	data := url.Values{}
	data.Set("grant_type", "authorization_code")
	data.Set("code", code)
	data.Set("redirect_uri", redirectURI)

	resp, err := http.PostForm(tokenURL, data)
	if err != nil {
		return nil, fmt.Errorf("token request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("token request failed with status %d", resp.StatusCode)
	}

	var tokenResp TokenResponse
	if err := json.NewDecoder(resp.Body).Decode(&tokenResp); err != nil {
		return nil, fmt.Errorf("failed to decode token response: %w", err)
	}

	return &tokenResp, nil
}

// generateState generates a random state string for CSRF protection.
func generateState() (string, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return base64.URLEncoding.EncodeToString(b), nil
}

// openBrowser opens the default browser to the specified URL.
func openBrowser(rawURL string) error {
	var cmd *exec.Cmd

	switch runtime.GOOS {
	case "darwin":
		cmd = exec.Command("open", rawURL)
	case "linux":
		cmd = exec.Command("xdg-open", rawURL)
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", rawURL)
	default:
		return fmt.Errorf("unsupported platform: %s", runtime.GOOS)
	}

	return cmd.Start()
}
