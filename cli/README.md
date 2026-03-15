# Preloop CLI

Command-line interface for managing AI agent policies, approvals, and tool configurations.

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/preloop/preloop.git
cd preloop/cli

# Build and install
make install

# Or build without installing
make build
./build/preloop --help
```

### Pre-built Binaries

Download the latest release from [GitHub Releases](https://github.com/preloop/preloop/releases).

## Quick Start

```bash
# Authenticate with a token
preloop auth login --token <your-token>

# Authenticate with a token and custom API URL
preloop auth login --token <your-token> --url http://localhost:8000

# Check authentication status
preloop auth status

# List policies
preloop policy list

# Validate a policy file
preloop policy validate my-policy.yaml

# Apply a policy
preloop policy apply my-policy.yaml

# List pending approvals
preloop approvals pending

# Approve a request
preloop approvals approve <request-id>
```

## Commands

### Authentication

```bash
preloop auth login --token <token>   # Save an API token
preloop auth login                   # OAuth browser flow (coming soon)
preloop auth logout                  # Log out and clear credentials
preloop auth status                  # Show authentication status
preloop auth token                   # Print token for scripting
```

### Policy Management

```bash
preloop policy list                    # List all policies
preloop policy validate <file>         # Validate a policy file
preloop policy apply <file>            # Apply a policy
preloop policy apply <file> --dry-run  # Preview changes without applying
preloop policy diff <file>             # Compare local vs remote policy
preloop policy export <name>           # Export a policy to file
```

### Tool Configuration

```bash
preloop tools list                     # List available tools
preloop tools list --enabled           # List only enabled tools
preloop tools enable <tool-name>       # Enable a tool
preloop tools disable <tool-name>      # Disable a tool
```

### Approvals

```bash
preloop approvals list                 # List all approvals
preloop approvals pending              # List pending approvals
preloop approvals approve <id>         # Approve a request
preloop approvals deny <id>            # Deny a request
```

### Agents

```bash
preloop agents discover                 # Interactive discovery; can prompt to onboard
preloop agents discover --json          # Emit discovery results as JSON
preloop agents discover --no-onboard-prompt
preloop agents discover --yes           # Auto-onboard newly discovered agents
preloop agents enroll openclaw        # Apply managed enrollment for OpenClaw
preloop agents enroll openclaw --dry-run
preloop agents enroll openclaw --yes   # Skip the confirmation prompt
preloop agents status openclaw         # Show local/remote managed state
preloop agents validate openclaw       # Validate the managed config
preloop agents restore openclaw        # Restore the most recent local backup
```

`preloop agents discover` is the starting point for agent onboarding. In interactive terminals it can prompt to onboard newly discovered agents one by one. Use `--no-onboard-prompt` to keep discovery read-only in scripts/CI, or `--yes` to auto-onboard all new candidates. `preloop agents enroll openclaw` remains the explicit mutating command.

Managed OpenClaw onboarding creates a durable managed credential, backs up the local config, replaces the local MCP config with a managed `preloop` entry, and may also import existing MCP servers plus rewrite supported model settings to Preloop's OpenAI-compatible gateway. Use `--dry-run` to preview changes first.

### Version

```bash
preloop version                        # Show version info
preloop version --check                # Check for updates
```

## Configuration

The CLI stores configuration in `~/.preloop/config.yaml`:

```yaml
access_token: <your-access-token>
refresh_token: <your-refresh-token>
api_url: http://localhost:8000
```

### Global Flags

All commands accept these flags:

- `--token <token>` - Override the access token for this invocation
- `--url <url>` - Override the API URL for this invocation
- `--verbose` / `-v` - Enable verbose output

### Environment Variables

- `PRELOOP_TOKEN` - Override the access token
- `PRELOOP_URL` - Override the API URL

### Resolution Priority

Both token and URL are resolved in this order (highest priority first):

1. CLI flags (`--token`, `--url`)
2. Environment variables (`PRELOOP_TOKEN`, `PRELOOP_URL`)
3. Config file (`~/.preloop/config.yaml`)
4. Defaults (`http://localhost:8000`)

## Development

### Prerequisites

- Go 1.22 or later
- Make

### Building

```bash
# Build for current platform
make build

# Cross-compile for all platforms
make build-all

# Run tests
make test

# Format code
make fmt

# Run linter
make lint
```

### Project Structure

```
cli/
├── cmd/
│   └── preloop/
│       └── main.go          # Entry point
├── internal/
│   ├── api/
│   │   └── client.go        # HTTP client for Preloop API
│   ├── config/
│   │   └── config.go        # Config management
│   ├── cmd/
│   │   ├── root.go          # Root command
│   │   ├── auth.go          # auth login/logout/status
│   │   ├── policy.go        # policy validate/apply/diff/export/list
│   │   ├── tools.go         # tools list/enable/disable
│   │   ├── approvals.go     # approvals list/pending/approve/deny
│   │   └── version.go       # version command
│   └── version/
│       └── check.go         # Daily version check logic
├── go.mod
├── go.sum
├── Makefile
└── README.md
```

## License

Apache License 2.0. See `../LICENSE`.
