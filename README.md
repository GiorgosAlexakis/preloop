# <img alt="Preloop Logo" src="frontend/public/assets/preloop-badge.png" style="height: 1.2em; margin-bottom: -.3em" /> Preloop - The MCP Governance Layer


[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

## Overview

Preloop is an open-source, event-driven automation platform with built-in human-in-the-loop safety. AI agents respond to events across your tools automatically. When agents call sensitive operations, Preloop intercepts the request and routes it for human approval.

Preloop acts as an MCP proxy and can be integrated in existing workflows without any infrastructure changes.

## Key Features

### Core Platform (Open Source)

- **Event-Driven Automation**: AI agents respond to events across your tools automatically
- **Human-in-the-Loop Safety**: Intercept sensitive operations and route for human approval
- **MCP Server**: Standards-based Model Context Protocol (MCP) server
  - 6 built-in tools: get_issue, create_issue, update_issue, search, estimate_compliance, improve_compliance
  - JWT authentication with per-user tool visibility
  - StreamableHTTP transport for Claude Code and other MCP clients
- **Tool Management**: Configure and manage tool access
  - Support for external MCP servers and tool proxying
  - Basic approval workflows (single-user) with email + mobile app notifications
- **Agentic Flows**: Event-driven workflows triggered by issue tracker events
- **Issue Tracker Integration**: Jira, GitHub, GitLab support with continuous sync
- **Vector Search**: Intelligent similarity search using embeddings
- **Duplicate Detection**: Automated detection of duplicate and overlapping issues
- **Compliance Metrics**: Evaluate issue compliance and get improvement recommendations
- **Web UI**: Modern interface built with Lit, Vite, and Shoelace Web Components

> **Looking for Enterprise features?** Preloop Enterprise Edition adds RBAC, team-based approvals, advanced audit logging, and more. See [Enterprise Features](#enterprise-features) below.

### Open Source vs Enterprise (important)

- **Open Source**: single-user approvals with **email + mobile app notifications**.
- **Enterprise**: adds **advanced conditions (CEL)**, **team-based approvals (quorum)**, **escalation**, and **Slack & Mattermost** notifications.
- **Mobile & Watch apps**: the iOS/Watch and Android apps can be used with **self-hosted / open-source** Preloop deployments.

## Supported Issue Trackers

- Jira Cloud and Server
- GitHub Issues
- GitLab Issues
- (More to be added in future releases, including Azure DevOps and Linear)

## Architecture

Preloop is designed with a modular architecture:

1.  **Preloop** (`./backend/preloop`): The main RESTful HTTP API server that provides access to issue tracking systems and vector search capabilities.
2.  **Preloop Models** (`./backend/preloop/models`): Contains the database models (using SQLAlchemy and Pydantic) and CRUD operations for interacting with the PostgreSQL database, including vector embeddings via PGVector.
3.  **Preloop Sync** (`./backend/preloop/sync`): A service responsible for polling configured issue trackers, indexing issues, projects, and organizations in the database, and updating issue embeddings.
4.  **Preloop Console** (`./frontend`): A web application built using Lit, Vite, TypeScript, and Shoelace Web Components.

This structure allows:
- Clear separation of concerns between the API layer, data models, and synchronization logic.
- Independent development and versioning of the core components.

## Preloop Console

The Preloop Console is in the `frontend` directory. It is built using modern web technologies to provide a fast, responsive, and feature-rich user experience.

- **Technology Stack**: Lit, Vite, TypeScript, and Material Web Components.

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- PGVector extension for PostgreSQL (for vector search capabilities)

### Local Setup

```bash
# Clone the repository
git clone https://github.com/spacecode/preloop.git
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

### Docker Setup

```bash
# Clone the repository
git clone https://github.com/spacecode/preloop.git
cd preloop

# Run with Docker Compose
docker-compose up
```

### Kubernetes Setup

Preloop can be deployed to Kubernetes using the provided Helm chart:

```bash
# Add the Spacecode Helm repository (if available)
# helm repo add spacecode https://charts.spacecode.ai
# helm repo update

# Install from the local chart
helm install preloop ./helm/preloop

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

Preloop provides a RESTful API with the following key endpoints:

### Authentication
- `POST /api/v1/auth/token` - Get authentication token
- `POST /api/v1/auth/refresh` - Refresh authentication token

### MCP Server Management
- `GET /api/v1/mcp-servers` - List configured MCP servers
- `POST /api/v1/mcp-servers` - Add new MCP server
- `PUT /api/v1/mcp-servers/{id}` - Update MCP server configuration
- `DELETE /api/v1/mcp-servers/{id}` - Remove MCP server
- `POST /api/v1/mcp-servers/{id}/scan` - Trigger tool discovery scan
- `GET /api/v1/mcp-servers/{id}/tools` - List tools available on server

### Tool Configuration
- `GET /api/v1/tool-configurations` - List tool configurations
- `POST /api/v1/tool-configurations` - Create tool configuration
- `PUT /api/v1/tool-configurations/{id}` - Update tool configuration
- `DELETE /api/v1/tool-configurations/{id}` - Delete tool configuration

### Approval Management
- `GET /api/v1/approval-policies` - List approval policies
- `POST /api/v1/approval-policies` - Create approval policy
- `PUT /api/v1/approval-policies/{id}` - Update approval policy
- `DELETE /api/v1/approval-policies/{id}` - Delete approval policy
- `GET /api/v1/approval-requests` - List approval requests (authenticated)
- `GET /api/v1/approval-requests/{request_id}` - Get approval request details (authenticated)
- `POST /api/v1/approval-requests/{request_id}/approve` - Approve request (authenticated)
- `POST /api/v1/approval-requests/{request_id}/decline` - Decline request (authenticated)
- `POST /api/v1/approval-requests/{request_id}/decide` - Approve or decline request (authenticated)
- `GET /approval/{request_id}/data?token={token}` - Get approval request details (public, token-based)
- `POST /approval/{request_id}/decide?token={token}` - Approve or decline approval request (public, token-based)

### Flows
- `GET /api/v1/flows` - List flows
- `POST /api/v1/flows` - Create flow
- `GET /api/v1/flows/{id}` - Get flow details
- `PUT /api/v1/flows/{id}` - Update flow
- `DELETE /api/v1/flows/{id}` - Delete flow
- `GET /api/v1/flows/{id}/executions` - List flow executions
- `GET /api/v1/flows/executions/{id}` - Get execution details
- `GET /api/v1/flows/executions/{id}/logs` - Get execution logs (from container or database)
- `GET /api/v1/flows/executions/{id}/metrics` - Get execution metrics (tool calls, tokens, cost)

## Trackers
- `GET /api/v1/trackers` - List trackers
- `GET /api/v1/trackers/{tracker_id}` - Get tracker details
- `POST /api/v1/trackers` - Create tracker
- `PUT /api/v1/trackers/{tracker_id}` - Update tracker
- `DELETE /api/v1/trackers/{tracker_id}` - Delete tracker

### Organizations
- `GET /api/v1/organizations` - List organizations
- `GET /api/v1/organizations/{org_id}` - Get organization details
- `POST /api/v1/organizations` - Create organization
- `PUT /api/v1/organizations/{org_id}` - Update organization
- `DELETE /api/v1/organizations/{org_id}` - Delete organization

### Projects
- `GET /api/v1/organizations/{org_id}/projects` - List projects
- `GET /api/v1/projects/{project_id}` - Get project details
- `POST /api/v1/projects` - Create project
- `PUT /api/v1/projects/{project_id}` - Update project
- `DELETE /api/v1/projects/{project_id}` - Delete project
- `POST /api/v1/projects/test-connection` - Test project connection

### Issues
- `GET /api/v1/issues/search` - Search issues
- `POST /api/v1/issues` - Create issue
- `GET /api/v1/issues/{issue_id}` - Get issue details
- `PUT /api/v1/issues/{issue_id}` - Update issue
- `DELETE /api/v1/issues/{issue_id}` - Delete issue
- `POST /api/v1/issues/{issue_id}/comments` - Add comment to issue

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

The Preloop API now includes integrated MCP tool endpoints with dynamic tool filtering, allowing any HTTP-based MCP client to connect directly. This is the recommended way to automate issue management workflows.

**Authentication:** All MCP endpoints use the same Bearer Token authentication as the rest of the API.

**Dynamic Tool Visibility:** MCP tools are only visible when your account has one or more trackers configured. This ensures tools have the necessary context to operate effectively. If you connect with an account that has no trackers, you will see an empty tool list.

**Connecting with Claude Code:**

You can connect Claude Code directly to your Preloop instance using the `claude mcp add` command.

1.  **Get your Preloop API Key:** You can find or create an API key in your Preloop user settings.
2.  **Add the MCP Server:** Run the following command, replacing `YOUR_PRELOOP_URL` and `YOUR_API_KEY` with your details.

    ```bash
    claude mcp add \
      --transport http \
      --header "Authorization: Bearer YOUR_API_KEY" \
      preloop \
      https://YOUR_PRELOOP_URL/mcp/v1
    ```

    - `--transport http`: Specifies that the server uses the HTTP transport.
    - `--header "Authorization: Bearer YOUR_API_KEY"`: Provides the necessary authentication header for all requests.
    - `preloop`: This is the name you will use to refer to the server (e.g., `@preloop get_issue ...`).
    - `https://YOUR_PRELOOP_URL/mcp/v1`: This is the base URL for the Preloop MCP endpoints.

**Example Workflow (using `curl`):**

If you are not using an MCP client and want to interact with the tool endpoints directly, you can use any HTTP client like `curl`.

1.  **Create an Issue:**
    ```bash
    curl -X POST "https://YOUR_PRELOOP_URL/api/v1/mcp/create_issue" \
    -H "Authorization: Bearer YOUR_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "project": "your-org/your-project",
      "title": "New Feature Request",
      "description": "Add a dark mode to the dashboard."
    }'
    ```

### Tool Approval Workflows

Preloop provides approval workflows for tool execution. Control which operations require approval before execution.

**Key Concepts:**
- **Tool Configuration**: Enable/disable tools and assign approval policies
- **Approval Policies**: Define approval requirements, approvers, timeouts, and notification channels
- **Email Notifications**: Receive approval requests via email with one-click approve/decline

**Example: Create an Approval Policy**

```bash
curl -X POST "https://YOUR_PRELOOP_URL/api/v1/approval-policies" \
-H "Authorization: Bearer YOUR_API_KEY" \
-H "Content-Type: application/json" \
-d '{
  "name": "Critical Operations",
  "description": "Require approval for critical issue operations",
  "is_default": false,
  "approver_user_ids": ["user-id-1", "user-id-2"],
  "approvals_required": 1,
  "timeout_seconds": 600,
  "notification_channels": ["email"]
}'
```

**Configure a tool to require approval:**

```bash
curl -X POST "https://YOUR_PRELOOP_URL/api/v1/tool-configurations" \
-H "Authorization: Bearer YOUR_API_KEY" \
-H "Content-Type: application/json" \
-d '{
  "tool_name": "update_issue",
  "tool_source": "preloop_builtin",
  "is_enabled": true,
  "approval_policy_id": "<policy_id_from_above>"
}'
```

> **Enterprise Features**: Preloop Enterprise Edition adds CEL-based conditional approvals, team-based approvals with quorum, escalation policies, and multi-channel notifications (Slack, Mattermost, mobile push). Contact sales@spacecode.ai for more information.

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

## Enterprise Features

Preloop Enterprise Edition extends the open-source core with additional features for teams and organizations:

| Feature | Open Source | Enterprise |
|---------|:-----------:|:----------:|
| MCP Server with 6 built-in tools | ✅ | ✅ |
| Basic approval workflows | ✅ | ✅ |
| Email notifications | ✅ | ✅ |
| Mobile app notifications (iOS/Watch; Android) | ✅ | ✅ |
| Issue tracker integration | ✅ | ✅ |
| Vector search & duplicate detection | ✅ | ✅ |
| Agentic flows | ✅ | ✅ |
| Web UI | ✅ | ✅ |
| **Role-Based Access Control (RBAC)** | ❌ | ✅ |
| **Team management** | ❌ | ✅ |
| **CEL conditional approval policies** | ❌ | ✅ |
| **Team-based approvals with quorum** | ❌ | ✅ |
| **Approval escalation** | ❌ | ✅ |
| **Slack notifications** | ❌ | ✅ |
| **Mattermost notifications** | ❌ | ✅ |
| **Admin dashboard** | ❌ | ✅ |
| **Audit logging & impersonation tracking** | ❌ | ✅ |
| **Billing & subscription management** | ❌ | ✅ |
| **Priority support** | ❌ | ✅ |

Contact sales@spacecode.ai for Enterprise Edition licensing.

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
