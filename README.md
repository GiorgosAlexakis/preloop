# <img alt="Preloop Logo" src="frontend/public/assets/preloop-badge.png" style="height: 21px;" height="18px" /> Preloop: AI Safety, Control, and Observability for AI Agents

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Preloop is an AI safety and control platform for teams deploying AI agents into real workflows. It gives you policy enforcement, human approvals, observability, budget controls, and audit trails across both tool use and model traffic.

Use Preloop as an MCP-native governance layer for tool access, an OpenAI-compatible and Anthropic-compatible gateway for managed model traffic, and a control plane for runtime identity, usage attribution, and operator visibility.


  <a href="https://youtu.be/yTtXn8WibTY" target="_blank" title="Watch the video">
    <img alt="Preloop Logo" src="frontend/public/assets/mcp-firewall.svg" alt="Watch the video" style="width: 100%; max-width: 1135px;" />
  </a>

**Works with OpenClaw, OpenCode, Claude Code, Codex CLI, Gemini CLI, Cursor, and any MCP-compatible agent or managed runtime.**

> **Read the official documentation:** Full guides and tutorials are available at [docs.preloop.ai](https://docs.preloop.ai).

## Why Preloop?

AI agents like Claude Code, Cursor, and OpenClaw are transforming how we work. But with great power comes great risk:

- **Accidental deletions.** One wrong command and your production database is gone.
- **Leaked secrets.** API keys pushed to public repos before anyone notices.
- **Runaway costs.** Agents spinning up expensive resources without limits.
- **Breaking changes.** Untested deployments to production at 3am.

Most teams face an impossible choice: give AI full access and move fast (but dangerously), or lock everything down and lose the productivity gains.

**Preloop solves this.** You can govern what agents are allowed to do, route risky actions to the right human workflow, track every important decision, and keep model usage and spend visible in one place. You stay in control while AI handles the routine work.

## Core Capabilities

### Access Policies

Define fine-grained access controls for any AI tool or operation:

- Tools support multiple ordered **access rules** (not just simple approval/deny)
- Rules are evaluated in priority order; first matching rule wins
- Each rule has an action (allow/deny/require_approval), optional CEL condition, and optional denial message
- Rules can be reordered via drag-and-drop in the UI

### Approval Workflows

When AI attempts a protected operation, Preloop pauses and notifies you:

- **Instant notifications** via mobile app, email, Slack, or Mattermost
- **One-tap approvals** from your phone, watch, or desktop
- **Async approval mode** — tool returns immediately with a polling handle; the agent polls `get_approval_status` until approved, then receives the tool result (Enterprise)
- **Per-tool justification** — require or optionally request agents to explain *why* a tool is being called before approval (Enterprise)
- **Team-based approvals** with quorum requirements (Enterprise)
- **Escalation policies** for time-sensitive operations (Enterprise)

<div align="center">
  <video src="https://docs.preloop.ai/assets/animations/quickstart/access_rules.mp4" controls autoplay loop muted style="max-height: 480px; width: auto; max-width: 100%; border-radius: 8px; margin-right:10px;"></video>
  <video src="https://docs.preloop.ai/assets/animations/quickstart/mobile_approval.mp4" controls autoplay loop muted style="max-height: 480px; width: auto; max-width: 100%; border-radius: 8px; margin-left:10px;"></video>
</div>


### Policy-as-Code

Define policies in YAML, manage via CLI or API:

```yaml
# Example: Require approval for production deployments
version: "1.0"
metadata:
  name: "Production Safeguards"
  description: "Require approval before deploying to production"
  tags: [security, production]

approval_workflows:
  - name: "deploy-approval"
    timeout_seconds: 600
    required_approvals: 1
    async_approval: true          # Agent polls instead of blocking

tools:
  - name: "bash"
    source: mcp
    approval_workflow: "deploy-approval"
    justification: required        # Agent must explain the call
    conditions:
      - expression: "args.command.contains('deploy') && args.command.contains('production')"
        action: require_approval
        description: "Production deployments require approval"
```

- **Version control** your policies alongside your code
- **GitOps workflows** for policy changes
- **CLI management** for automation and scripting
- **API access** for programmatic policy management

### Complete Audit Trail

Every AI action is logged with full context:

- What was attempted (tool, parameters, context)
- Which policy matched and why
- Who approved or rejected (and when)
- Execution result and duration

Essential for security reviews, compliance, and debugging.

### AI Model Gateway

Preloop can terminate model traffic on behalf of managed runtimes instead of handing provider credentials directly to agent containers:

- OpenAI-compatible gateway endpoints: `GET /openai/v1/models`, `POST /openai/v1/chat/completions`, `POST /openai/v1/responses`
- Anthropic-compatible gateway endpoint: `POST /anthropic/v1/messages`
- SSE streaming support for chat completions and responses
- Per-request attribution to account, flow, flow execution, API key, and runtime principal
- Token and estimated-cost accounting persisted to the gateway usage ledger
- Account-level and flow-level budget enforcement with soft-limit annotations and hard stops
- Subject-scoped allowed-model enforcement for managed-agent and API-key traffic
- Product-facing usage summary endpoints for account and flow monitoring
- Account-scoped runtime session explorer endpoints for browsing managed sessions beyond flows
- Dashboard telemetry for active runtime sessions, recent tool calls, and daily model spend
- Execution-scoped gateway event inspection via `GET /api/v1/flows/executions/{execution_id}/gateway-events`
- Console surfaces for browsing recent runtime sessions and searching captured gateway interactions

### Managed Agent Onboarding

Preloop can discover and onboard existing local agents into the same control plane.

- Start with `preloop agents discover`
- Supported discovery targets include **OpenClaw**, **OpenCode**, **Claude Code**, **Codex CLI**, and **Gemini CLI**
- Discovery is the entry point for managed onboarding and local-config inspection
- On supported managed onboarding paths, Preloop can import the agent's configured AI models and MCP tools into your Preloop account
- Preloop can then reconfigure the local agent to use the **Preloop Gateway** for model traffic and the **Preloop Tool Firewall** for governed tool access

For OpenClaw, `preloop agents discover` can prompt to onboard newly discovered agents, while `preloop agents enroll openclaw` remains the explicit managed enrollment command. That flow can import the current model into Preloop, rewrite supported model settings to Preloop's OpenAI-compatible gateway, and reduce the local MCP config to a single managed `preloop` entry with backup/restore support.

### Subject-Scoped Governance

Preloop can apply governance rules at multiple subject layers instead of only at the account level:

- Account defaults remain the broad fallback for tools and model access
- Managed-agent governance can narrow tool visibility, tool rules, and model access for one enrolled runtime
- API-key governance can further narrow behavior for one token, taking precedence over the managed-agent scope when both are present
- Subject-scoped settings can control `allowed_models`, per-model budget metadata, ordered tool access rules, and explicit tool enable/disable overrides

This subject context is propagated consistently through MCP tool listing, policy evaluation, and model gateway budget checks so one runtime token only sees and uses the tools and models intended for it.

### Runtime Sessions and Managed Agents

Preloop distinguishes between durable runtime identities and individual runtime sessions:

- `ManagedAgent` is the durable identity for an enrolled CLI or desktop agent
- `RuntimeSession` is the per-session activity record used for live status, recent activity, and observability
- `session_source_type` and `session_source_id` identify where a session came from
- `runtime_principal_type`, `runtime_principal_id`, and `runtime_principal_name` identify the durable owner of the session

This separation lets one enrolled agent accumulate multiple sessions over time while preserving searchable gateway usage, MCP activity, audit events, and operator lifecycle controls per session.

### Secret Custody

Preloop now stores AI model credentials behind a provider-agnostic secret abstraction:

- Built-in `local_encrypted` backend for simple self-hosted deployments
- Hash-only runtime API tokens for flow executions
- Optional external secret backend path for Vault/OpenBao-compatible KV v2 stores
- Agent runtimes can receive short-lived Preloop gateway tokens instead of provider secrets

## Comparison with AWS Agent Core

| Feature | Preloop | AWS Agent Core |
|---------|:-------:|:--------------:|
| Open source | ✅ | ❌ |
| Self-hosted option | ✅ | ❌ |
| Policy-as-code (YAML) | ✅ | Limited |
| MCP native | ✅ | ❌ |
| Works with any agent | ✅ | AWS-focused |
| Human approval workflows | ✅ | ✅ |
| Audit trail | ✅ | ✅ |
| CLI management | ✅ | AWS CLI |
| GitOps-friendly | ✅ | Limited |
| Mobile app approvals | ✅ | ❌ |
| Team-based approvals | ✅ (Enterprise) | ✅ |

**Preloop is the open-source alternative to AWS Agent Core** for teams who want vendor-neutral, self-hosted AI governance.

```
AI Agent -> Preloop -> [Policy check] -> Allow / Deny / Require Approval -> Execute
```

**How it works:**
1. Define policies for each tool: allow, deny, or require approval
2. Policies can be fine-grained, checking parameter values and context
3. AI agents call tools through Preloop's MCP proxy
4. Actions are allowed, denied, or paused for approval based on your policies
5. Full audit trail of every action and decision


## Key Features

### Safety & Control

- **Policy Engine.** Define allow, deny, and approval workflows for any tool or action.
- **Access Rules.** Multiple ordered rules per tool with allow/deny/require approval actions.
- **Drag-and-Drop Priority.** Reorder rule evaluation priority visually.
- **Fine-Grained Rules.** Policies can check tool names, parameter values, and context.
- **Instant Notifications.** Get alerts on mobile, email, Slack, or Mattermost.
- **One-Tap Approvals.** Approve or reject from your phone, watch, or desktop.
- **Full Audit Trail.** Complete log of every AI action and policy decision.
- **Async Approval Mode.** Non-blocking approval: tool returns immediately, agent polls `get_approval_status` until the human decides.
- **Per-Tool Justification.** Require agents to provide a reason for each tool call. Mode: `required` (blocks without it) or `optional` (agent may provide one).
- **Flexible Conditions.** Use CEL expressions for context-aware rules (Enterprise).
- **AI Approval (Enterprise).** AI-driven approval with configurable model, prompt, confidence threshold, and fallback behavior.
- **Team Approvals.** Require quorum from multiple team members for critical ops (Enterprise).

### Integration & Compatibility

- **MCP Proxy.** Works with any Model Context Protocol-compatible AI agent.
- **Zero Infrastructure Changes.** Drop-in solution, no code modifications needed.
- **Built-in Tools.** 11 tools for issue and PR/MR management included.
- **External MCP Servers.** Proxy any external MCP server through Preloop's safety layer.
- **Issue Tracker Sync.** Connect Jira, GitHub, GitLab for full context.

### Automation Platform

- **Agentic Flows.** Build event-driven workflows triggered by webhooks, schedules, or tracker events.
- **Gateway-Routed Model Access.** Managed flows can use a Preloop-owned model gateway for centralized cost controls, telemetry, and key custody.
- **Vector Search.** Intelligent similarity search using embeddings.
- **Duplicate Detection.** Automatically identify overlapping issues.
- **Compliance Metrics.** Evaluate and improve issue quality.
- **Web UI.** Modern interface built with Lit, Vite, and Shoelace.

> **Looking for Enterprise features?** Preloop Enterprise Edition adds RBAC, team-based approvals, advanced audit logging, and more. See [Enterprise Features](#enterprise-features) below.

### Open Source vs Enterprise (important)

- **Open Source**: single-user approvals with **email, mobile app, Slack, and Mattermost notifications**.
- **Enterprise**: adds **advanced conditions (CEL)**, **team-based approvals (quorum)**, and **escalation**.
- **Mobile & Watch apps**: the iOS/Watch and Android apps can be used with **self-hosted / open-source** Preloop deployments.

## Supported Issue Trackers

- Jira Cloud and Server
- GitHub Issues
- GitLab Issues
- (More to be added in future releases, including Azure DevOps and Linear)

## Architecture

Preloop features a modular architecture designed to provide a secure control plane for AI agents, separating the core API server, database models, backend synchronization services, and the web frontend console.

For a complete conceptual overview of the system components, data flows, and infrastructure, please see the [Architecture Document](ARCHITECTURE.md).

## Frontend & CLI

- **Preloop Console (Frontend):** Located in the `frontend` directory, the web interface gives you governance controls, tool management, and dashboard visibility. See [frontend/README.md](frontend/README.md) for details.
- **Preloop CLI:** Manage policies and system state from the command line. See [cli/README.md](cli/README.md) for usage.

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- PGVector extension for PostgreSQL (for vector search capabilities)

### Local Setup

```bash
# Clone the repository
git clone https://github.com/preloop/preloop.git
cd preloop

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Set up the database

# Configure your environment
cp .env.example .env
# Edit .env with your settings
```

## Configuration

### Environment Variables

Preloop is configured via environment variables. Copy `.env.example` to `.env` and customize as needed.

#### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost/preloop` | PostgreSQL connection string |
| `SECRET_KEY` | (required) | Secret key for JWT tokens |
| `ENVIRONMENT` | `development` | Environment (development, production) |
| `LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `ROOT_LOG_LEVEL` | `WARNING` | Root logger verbosity level |

#### Model Gateway & Secrets

| Variable | Default | Description |
|----------|---------|-------------|
| `PRELOOP_MODEL_GATEWAY_URL` | `http://host.docker.internal:8000/openai/v1` | Default gateway URL injected into gateway-enabled runtimes |
| `MODEL_GATEWAY_CAPTURE_CONTENT` | `false` | Include truncated content previews in emitted model-call events |
| `MODEL_GATEWAY_MAX_PREVIEW_CHARS` | `512` | Max characters retained when content capture is enabled |
| `VAULT_KV_V2_ENABLED` | `false` | Enable the optional Vault/OpenBao-compatible KV v2 secret backend |
| `VAULT_KV_V2_URL` | unset | Base URL for the external secret backend |
| `VAULT_KV_V2_TOKEN` | unset | Access token for the external secret backend |
| `VAULT_KV_V2_NAMESPACE` | unset | Optional namespace header for Vault/OpenBao |
| `VAULT_KV_V2_MOUNT` | `secret` | KV v2 mount name |
| `VAULT_KV_V2_PATH_PREFIX` | unset | Optional path prefix applied to external secret references |

#### Feature Flags

| Variable | Default | Description |
|----------|---------|-------------|
| `REGISTRATION_ENABLED` | `true` | Enable self-registration. Set to `false` to disable public signups and require admin invitation. |

#### Disabling Self-Registration

For private deployments where you want to control who can access the system:

```bash
# In your .env file or Docker environment
REGISTRATION_ENABLED=false
```

When registration is disabled:
- The "Sign Up" button is hidden from the UI
- The `/register` page redirects to `/login`
- **The `/api/v1/auth/register` API endpoint returns 403 Forbidden** - preventing direct API registration attempts
- New users must be invited by an administrator

**Security Note**: With `REGISTRATION_ENABLED=false`, the backend API enforces the restriction at the endpoint level. Any attempt to register via the API (including scripts or direct HTTP requests) will be rejected with a 403 status code.

To invite users when registration is disabled, use the admin API or CLI (Enterprise Edition includes a full admin dashboard for user management).

#### GitHub App (Optional)

For enhanced GitHub integration including PR status checks and bot reactions:

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_APP_ID` | | GitHub App ID (from app settings page) |
| `GITHUB_APP_SLUG` | | GitHub App slug (the URL-friendly name) |
| `GITHUB_APP_PRIVATE_KEY` | | Base64-encoded private key from GitHub App |
| `GITHUB_APP_CLIENT_ID` | | OAuth client ID for user authentication |
| `GITHUB_APP_CLIENT_SECRET` | | OAuth client secret |
| `GITHUB_APP_WEBHOOK_SECRET` | | Secret for verifying webhook payloads |

These are optional and only needed if you're using a GitHub App for authentication or advanced features like reaction management on PRs.

#### OAuth Sign-In (Enterprise)

Enable OAuth sign-in/sign-up via GitHub, Google, and/or GitLab. Users can authenticate with their existing provider accounts instead of creating a Preloop-specific password.

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_OAUTH_CLIENT_ID` | | Google OAuth 2.0 client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | | Google OAuth 2.0 client secret |
| `GITLAB_OAUTH_CLIENT_ID` | | GitLab OAuth client ID |
| `GITLAB_OAUTH_CLIENT_SECRET` | | GitLab OAuth client secret |
| `GITLAB_OAUTH_BASE_URL` | `https://gitlab.com` | GitLab instance URL (for self-hosted) |

GitHub OAuth sign-in reuses the GitHub App credentials above. Enable via Helm values:

```yaml
mcpOauth:
  enabled: true
googleOauth:
  enabled: true
  clientId: "your-google-client-id"
  clientSecret: "your-google-client-secret"
gitlabOauth:
  enabled: true
  clientId: "your-gitlab-client-id"
  clientSecret: "your-gitlab-client-secret"
```

**Supported flows:**
- **GitHub**: Sign-in + automatic tracker setup prompt
- **Google**: Sign-in only (no tracker created)
- **GitLab**: Sign-in + automatic tracker setup prompt

#### MCP OAuth 2.1 Server

Preloop includes a built-in OAuth 2.1 Authorization Server for MCP client authentication (e.g., Claude Desktop). This is enabled automatically when `mcpOauth.enabled=true`.

| Variable | Default | Description |
|----------|---------|-------------|
| `PRELOOP_URL` | `http://localhost:8000` | Public URL of your Preloop instance (used for OAuth discovery endpoints) |

**Discovery endpoints:**
- `GET /.well-known/oauth-authorization-server` — RFC 8414 metadata
- `GET /.well-known/oauth-protected-resource` — RFC 9728 metadata

**OAuth endpoints:**
- `POST /oauth/register` — Dynamic Client Registration (RFC 7591)
- `GET /oauth/authorize` — Authorization endpoint (redirects to consent page)
- `POST /oauth/token` — Token exchange (Authorization Code + PKCE for MCP, JWT for CLI)
- `POST /oauth/revoke` — Token revocation

The CLI also uses these endpoints. `preloop login` honors `PRELOOP_URL`, uses a loopback callback on local machines, and falls back to a copy/paste authorization-code flow on SSH or headless hosts.

### Docker Setup

```bash
# Clone the repository
git clone https://github.com/preloop/preloop.git
cd preloop

# Run the full development stack (backend + workers + frontend with HMR)
docker compose up

# Run with tagged release images (production)
PRELOOP_VERSION=0.9.0-rc.0 SECRET_KEY=$(openssl rand -hex 32) \
  docker compose -f docker-compose.release.yaml up -d
```

Quick installers are also available:

```bash
# Install the standalone CLI
curl -fsSL https://preloop.ai/install/cli | sh

# Install the OSS stack
curl -fsSL https://preloop.ai/install/oss | sh
```

Set `PRELOOP_VERSION=0.9.0-rc.0 before either command to pin a specific release, or use `https://preloop.ai/install/<script>?version=0.9.0-rc.0`.

The default `docker compose up` command uses `docker-compose.override.yml` for local development, so source changes in `backend/` and `frontend/` are mounted directly into the containers. The frontend runs via Vite on `http://localhost:5173`, while the backend API stays on `http://localhost:8000`.

See [`docker-compose.release.yaml`](docker-compose.release.yaml) for full configuration and required environment variables.

#### Release Management

Use the release script to prepare a new version across the main release surfaces:

```bash
./scripts/release.sh 0.9.0-rc.0
```

The script can also optionally commit the release prep, create and push `v<version>`, and watch the GitHub `Release` workflow with `gh`.

See [`RELEASING.md`](RELEASING.md) for the full checklist and [`scripts/release.sh`](scripts/release.sh) for the release prep helper.

### Kubernetes Setup

Preloop can be deployed to Kubernetes using the provided Helm chart:

```bash
# Add the Spacecode Helm repository (if available)
# helm repo add spacecode https://charts.spacecode.ai
# helm repo update

# Install from the local chart
helm install preloop ./helm/preloop

# Or install the packaged chart from a GitHub release
# helm install preloop https://github.com/preloop/preloop/releases/download/v0.8.0-beta.3/preloop-0.8.0-beta.3.tgz

# Or install with custom values
helm install preloop ./helm/preloop --values custom-values.yaml
```

For more details about the Helm chart, see the [chart README](./helm/preloop/README.md).

## Usage

### Starting the Server

1.  **Set Environment Variables:**
    Ensure you have a `.env` file configured with the necessary environment variables (see `.env.example`). Key variables include database connection details, API keys, etc.

2.  **Start Preloop API:**
    Use the provided script to start the main API server:
    ```bash
    ./start.sh
    ```
    This script typically handles activating the virtual environment and running the server (e.g., `python -m preloop.server`).

3.  **Start Preloop Sync Service:**
    In a separate terminal, start the synchronization service to begin indexing data from your configured trackers:
    ```bash
    # Activate the virtual environment if not already active
    # source .venv/bin/activate
    preloop-sync scan all
    ```
    This command tells Preloop Sync to scan all configured trackers and update the database.

### API Documentation

When running, the API documentation is available at:

```
http://localhost:8000/docs
```

The OpenAPI specification is also available at:

```
http://localhost:8000/openapi.json
```

### Using the REST API

Preloop provides a RESTful HTTP API:

```python
import requests
import json

# Base URL for the Preloop API
base_url = "http://localhost:8000/api/v1"

# Authenticate and get a token
auth_response = requests.post(
    f"{base_url}/auth/token",
    json={"username": "your-username", "password": "your-password"}
)
token = auth_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Test a tracker connection
connection = requests.post(
    f"{base_url}/projects/test-connection",
    headers=headers,
    json={
        "organization": "spacecode",
        "project": "astrobot"
    }
)
print(json.dumps(connection.json(), indent=2))

# Search for issues related to authentication
results = requests.get(
    f"{base_url}/issues/search",
    headers=headers,
    params={
        "organization": "spacecode",
        "project": "astrobot",
        "query": "authentication problems",
        "limit": 5
    }
)
print(json.dumps(results.json(), indent=2))

# Create a new issue
issue = requests.post(
    f"{base_url}/issues",
    headers=headers,
    json={
        "organization": "spacecode",
        "project": "astrobot",
        "title": "Improve login error messages",
        "description": "Current error messages are not clear enough...",
        "labels": ["enhancement", "authentication"],
        "priority": "High"
    }
)
print(json.dumps(issue.json(), indent=2))
```

## API Endpoints

Preloop provides a comprehensive REST API for authentication, tool management, approval workflows, policy generation, and integrations.

For the complete REST API reference, including interactive Swagger endpoints, please see the [official API documentation](https://docs.preloop.ai/api/).

### Unified WebSocket

Preloop uses a unified WebSocket connection for real-time updates across the application:

**Connection:** `ws://localhost:8000/api/v1/ws/unified`

**Message Routing:**
- Flow execution updates (`flow_executions` topic)
- Approval request notifications (`approvals` topic)
- System activity updates (`activity` topic)
- Session events (`system` topic)

**Features:**
- Automatic reconnection with exponential backoff
- Pub/sub message routing to subscribers
- Topic-based filtering for efficient message delivery
- Session management with activity tracking
- Heartbeat monitoring

**Usage in Frontend:**
```typescript
import { unifiedWebSocketManager } from './services/unified-websocket-manager';

// Subscribe to flow execution updates
const unsubscribe = unifiedWebSocketManager.subscribe(
  'flow_executions',
  (message) => console.log('Flow update:', message),
  (message) => message.execution_id === myExecutionId  // Optional filter
);

// Clean up when done
unsubscribe();
```

### Using MCP Tools via API

The Preloop API includes integrated MCP tool endpoints with dynamic tool filtering, allowing any HTTP-based MCP client to connect directly.

[Read the MCP Integration Guide in docs.preloop.ai](https://docs.preloop.ai) for details on authenticating clients like Claude Code, Cursor, and Windsurf, and setting up workflows or timeouts.

### Mobile Push Notifications (iOS/Android)

Open-source users can enable mobile push notifications by proxying requests through the production Preloop server at https://preloop.ai.

**Setup Steps:**

1. **Create an account** at https://preloop.ai
2. **Generate an API key** with `push_proxy` scope from the Settings page
3. **Configure your instance** with these environment variables:

```bash
# Push notification proxy configuration
PUSH_PROXY_URL=https://preloop.ai/api/v1/push/proxy
PUSH_PROXY_API_KEY=your-api-key-here
```

4. **Enable push notifications** in the Notification Preferences page in your Preloop Console
5. **Register your mobile device** by scanning the QR code shown in Notification Preferences

Once configured, approval requests will trigger push notifications on your registered iOS or Android devices.

> **Note**: The mobile apps (iOS/Watch and Android) are designed to work with self-hosted Preloop instances. They connect to your server URL extracted from the QR code.

### Version Checking & Updates

By default, Preloop checks for version updates by contacting https://preloop.ai on startup and once daily. This helps you stay informed about new releases and security updates.

**Privacy**: Only instance UUID, version number, and IP address are sent. No user data is transmitted.

**Opt-out**: Set `PRELOOP_DISABLE_TELEMETRY=true` or `DISABLE_VERSION_CHECK=true` to disable version checking and telemetry entirely.

For detailed architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Testing

Preloop uses pytest for unit and integration testing. The test suite covers API endpoints, database models, and tracker integrations.

### Running Tests

To run all tests:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/endpoints/test_webhooks.py

# Run a specific test case
pytest tests/endpoints/test_webhooks.py::TestWebhooksEndpoint::test_github_webhook_valid_signature
```

### Test Structure

- **Unit Tests**: Located in `tests/` directory, testing individual components in isolation
- **Integration Tests**: Test the interaction between components
- **Endpoint Tests**: Test API endpoints with mocked database sessions

### Testing Webhooks

The webhook endpoint tests (`tests/endpoints/test_webhooks.py`) validate:

1. Authentication via signatures/tokens for GitHub and GitLab webhooks
2. Error handling for invalid signatures, missing tokens, etc.
3. Organization identifier resolution
4. Database updates (last_webhook_update timestamp)
5. Error handling for database failures

These tests use mocking to isolate the webhook handling logic from external dependencies.

## Roadmap

Preloop is evolving into a comprehensive control plane for AI agents. Here's what's coming:

- 🔜 **Agent Registry** — Register, credential, and manage AI agents as first-class entities
- 🔜 **AI Model Gateway** — Unified model proxy with cost tracking, rate limits, and usage analytics
- 🔜 **Agent Monitoring** — Real-time visibility into agent activity, spending, and health
- 🔜 **Budget Controls** — Per-agent spending caps with alerts and enforcement

Star the repo and watch for updates!

## Enterprise Features

Preloop Enterprise Edition extends the open-source core with additional features for teams and organizations:

| Feature | Open Source | Enterprise |
|---------|:-----------:|:----------:|
| MCP Server with 11 built-in tools | ✅ | ✅ |
| Basic approval workflows | ✅ | ✅ |
| Email notifications | ✅ | ✅ |
| Mobile app notifications (iOS/Watch; Android) | ✅ | ✅ |
| Issue tracker integration | ✅ | ✅ |
| Vector search & duplicate detection | ✅ | ✅ |
| Agentic flows | ✅ | ✅ |
| Web UI | ✅ | ✅ |
| **Role-Based Access Control (RBAC)** | ❌ | ✅ |
| **Team management** | ❌ | ✅ |
| **CEL conditional approval workflows** | ❌ | ✅ |
| **Access rules with CEL conditions** | Basic (single condition) | Advanced (multiple conditions, AND/OR, CEL editor) |
| **AI-driven approval workflows** | ❌ | ✅ |
| **Team-based approvals with quorum** | ❌ | ✅ |
| **Async approval mode** | ✅ | ✅ |
| **Per-tool justification settings** | ✅ | ✅ |
| **Approval escalation** | ❌ | ✅ |
| Slack notifications | ✅ | ✅ |
| Mattermost notifications | ✅ | ✅ |
| **Admin dashboard** | ❌ | ✅ |
| **Audit logging & impersonation tracking** | ❌ | ✅ |
| **Billing & subscription management** | ❌ | ✅ |
| **Priority support** | ❌ | ✅ |

Contact sales@preloop.ai for Enterprise Edition licensing.

## Contributing

Contributions are welcome! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on how to get started.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

Preloop is open source software licensed under the [Apache License 2.0](LICENSE).

Copyright (c) 2026 Spacecode AI Inc.
