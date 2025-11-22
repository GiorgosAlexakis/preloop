# Preloop AI

![Preloop Logo](assets/logo.webp)

## Overview

Preloop is an event-driven automation platform with built-in human-in-the-loop safety. AI agents respond to events across your tools automatically. When agents call sensitive operations, Preloop intercepts the request and routes it for human approval—no infrastructure changes required.

## Key Features

- **Event-Driven Automation**: AI agents respond to events across your tools automatically
- **Human-in-the-Loop Safety**: When agents call sensitive operations, Preloop intercepts the request and routes it for human approval—no infrastructure changes required
- **MCP Server**: Standards-based Model Context Protocol (MCP) server with dynamic tool filtering
  - 6 built-in tools: get_issue, create_issue, update_issue, search, estimate_compliance, improve_compliance
  - JWT authentication with per-user tool visibility
  - StreamableHTTP transport for Claude Code and other MCP clients
- **Advanced Tool Management**: Configure and manage tool access with granular control
  - **Conditional Approval Policies**: Use CEL (Common Expression Language) to define conditional rules for tool execution
  - **Multi-tier Approval System**: Open-core edition with basic approvals; proprietary edition with advanced policies, quorum, escalation, and team-based approvals
  - Support for external MCP servers and tool proxying
  - Human-in-the-loop approval workflows for sensitive operations
- **Mobile Push Notifications**: Stay informed of approval requests and system events
  - **QR Code Registration**: Easy mobile device setup via Universal Links (iOS) and App Links (Android)
  - Firebase Cloud Messaging (FCM) for Android
  - Apple Push Notification Service (APNS) for iOS
  - Email notifications with one-click approve/decline
  - Deep linking support for seamless app-to-web transitions
- **Multi-User Accounts**: Team-based collaboration with role-based access control (RBAC)
  - User and team management
  - Custom roles and permissions
  - Invitation system with email verification
- **Agentic Flows**: Event-driven workflows triggered by issue tracker events with real-time monitoring
- **Issue Tracker Integration**: Continuous ingestion of issues, comments, projects, and organizations from Jira, GitHub, GitLab, and more
- **Vector Search**: Intelligent similarity search across issue trackers and projects using embeddings
- **Duplicate Detection**: Automated detection of duplicate and overlapping issues
- **Compliance Metrics**: Evaluate issue compliance and receive actionable improvement recommendations
- **Web UI**: Comprehensive interface built with Lit, Vite, and Material Web Components

## Supported Issue Trackers

- Jira Cloud and Server
- GitHub Issues
- GitLab Issues
- (More to be added in future releases, including Azure DevOps and Linear)

## Architecture

Preloop AI is designed with a modular architecture:

1.  **Preloop AI** (this repository): The main RESTful HTTP API server that provides access to issue tracking systems and vector search capabilities.
2.  **SpaceModels** (submodule `./SpaceModels`): Contains the database models (using SQLAlchemy and Pydantic) and CRUD operations for interacting with the PostgreSQL database, including vector embeddings via PGVector.
3.  **SpaceSync** (submodule `./spacesync`): A service responsible for polling configured issue trackers, indexing issues, projects, and organizations in the database, and updating issue embeddings.
4.  **SpaceLit** (submodule `./SpaceLit`): A web application built using Lit, Vite, TypeScript, and Shoelace Web Components.

This structure allows:
- Clear separation of concerns between the API layer, data models, and synchronization logic.
- Independent development and versioning of the core components.

## Frontend

The frontend is in the `SpaceLit` directory. It is built using modern web technologies to provide a fast, responsive, and feature-rich user experience.

- **Technology Stack**: Lit, Vite, TypeScript, and Material Web Components.

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- PGVector extension for PostgreSQL (for vector search capabilities)

### Local Setup

```bash
# Clone the repository
git clone https://github.com/spacecode/preloop-ai.git
cd preloop-ai

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

### Docker Setup

```bash
# Clone the repository
git clone https://github.com/spacecode/preloop-ai.git
cd preloop-ai

# Run with Docker Compose
docker-compose up
```

### Kubernetes Setup

Preloop AI can be deployed to Kubernetes using the provided Helm chart:

```bash
# Add the Spacecode Helm repository (if available)
# helm repo add spacecode https://charts.spacecode.ai
# helm repo update

# Install from the local chart
helm install preloop-ai ./helm/preloop-ai

# Or install with custom values
helm install preloop-ai ./helm/preloop-ai --values custom-values.yaml
```

For more details about the Helm chart, see the [chart README](./helm/preloop-ai/README.md).

## Usage

### Starting the Server

1.  **Set Environment Variables:**
    Ensure you have a `.env` file configured with the necessary environment variables (see `.env.example`). Key variables include database connection details, API keys, etc.

2.  **Start Preloop AI API:**
    Use the provided script to start the main API server:
    ```bash
    ./start.sh
    ```
    This script typically handles activating the virtual environment and running the server (e.g., `python -m spacebridge.server`).

3.  **Start SpaceSync Service:**
    In a separate terminal, start the synchronization service to begin indexing data from your configured trackers:
    ```bash
    # Activate the virtual environment if not already active
    # source .venv/bin/activate
    spacesync scan all
    ```
    This command tells SpaceSync to scan all configured trackers and update the database.

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

Preloop AI provides a RESTful HTTP API:

```python
import requests
import json

# Base URL for the Preloop AI API
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

Preloop AI provides a RESTful API with the following key endpoints:

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


### Admin Dashboard and API (not available in open source version)

Preloop AI includes a comprehensive admin dashboard for superusers to monitor system activity, manage users, and track resource usage.

**Admin Endpoints** (require superuser permissions):
- `GET /api/v1/admin/activity/sessions` - Get active WebSocket sessions with real-time activity
- `GET /api/v1/admin/accounts` - List all accounts with stats and filtering
- `GET /api/v1/admin/accounts/{id}` - Get detailed account information
- `GET /api/v1/admin/activity/stats` - Get system-wide activity statistics

**Managing Superusers:**

Use the provided management script to promote or demote superuser permissions:

```bash
# Promote a user to superuser
python scripts/manage_superusers.py promote user@example.com

# Demote a user from superuser
python scripts/manage_superusers.py demote user@example.com

# List all superusers
python scripts/manage_superusers.py list
```

**Admin Features:**
- Real-time session monitoring from in-memory session manager (no N+1 queries)
  - **Note**: In multi-pod deployments, each pod maintains its own session registry. The `/admin/activity/sessions` endpoint only shows sessions connected to the current pod. For cross-pod monitoring, query the Event table or aggregate results from all pod endpoints.
- User activity tracking and analytics
- Account management with subscription status
- Flow execution monitoring and debugging
- Audit log viewing (see Impersonation Auditing below)

### Unified WebSocket

Preloop AI uses a unified WebSocket connection for real-time updates across the application:

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

### Impersonation Auditing

Preloop AI tracks all user impersonation events for security and compliance. Administrators can audit impersonated sessions to trace actions back to the original operator.

**Audit Events:**
- `impersonation_started` - When an admin begins impersonating a user
- `impersonation_ended` - When impersonation session ends
- All actions during impersonation are logged with both impersonator and impersonated user IDs

**Viewing Audit Logs:**
```bash
# View audit logs for a specific user
curl -X GET "https://YOUR_SPACEBRIDGE_URL/api/v1/admin/audit-logs?user_id=USER_ID" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY"

# Filter by event type
curl -X GET "https://YOUR_SPACEBRIDGE_URL/api/v1/admin/audit-logs?event_type=impersonation_started" \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY"
```

**Tracing Impersonated Sessions:**
Each audit log entry includes:
- `impersonator_id`: The admin who initiated impersonation
- `impersonated_user_id`: The user being impersonated
- `session_id`: Links to session tracking for full activity trail
- `ip_address`, `user_agent`: Device and location information
- `event_data`: Additional context (target user, reason, etc.)

For more details, see [ARCHITECTURE.md](docs/ARCHITECTURE.md) section on audit logging and impersonation.

### Using MCP Tools via API

The Preloop AI API now includes integrated MCP tool endpoints with dynamic tool filtering, allowing any HTTP-based MCP client to connect directly. This is the recommended way to automate issue management workflows.

**Authentication:** All MCP endpoints use the same Bearer Token authentication as the rest of the API.

**Dynamic Tool Visibility:** MCP tools are only visible when your account has one or more trackers configured. This ensures tools have the necessary context to operate effectively. If you connect with an account that has no trackers, you will see an empty tool list.

**Connecting with Claude Code:**

You can connect Claude Code directly to your Preloop AI instance using the `claude mcp add` command.

1.  **Get your Preloop AI API Key:** You can find or create an API key in your Preloop AI user settings.
2.  **Add the MCP Server:** Run the following command, replacing `YOUR_PRELOOP_AI_URL` and `YOUR_API_KEY` with your details.

    ```bash
    claude mcp add \
      --transport http \
      --header "Authorization: Bearer YOUR_API_KEY" \
      preloop_ai \
      https://YOUR_PRELOOP_AI_URL/mcp/v1
    ```

    - `--transport http`: Specifies that the server uses the HTTP transport.
    - `--header "Authorization: Bearer YOUR_API_KEY"`: Provides the necessary authentication header for all requests.
    - `preloop_ai`: This is the name you will use to refer to the server (e.g., `@preloop_ai get_issue ...`).
    - `https://YOUR_PRELOOP_AI_URL/mcp/v1`: This is the base URL for the Preloop AI MCP endpoints.

**Example Workflow (using `curl`):**

If you are not using an MCP client and want to interact with the tool endpoints directly, you can use any HTTP client like `curl`.

1.  **Create an Issue:**
    ```bash
    curl -X POST "https://YOUR_PRELOOP_AI_URL/api/v1/mcp/create_issue" \
    -H "Authorization: Bearer YOUR_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "project": "your-org/your-project",
      "title": "New Feature Request",
      "description": "Add a dark mode to the dashboard."
    }'
    ```

### Tool Approval Workflows

Preloop AI provides sophisticated approval workflows for tool execution with conditional policies and multi-channel notifications. Control which operations require approval and define conditional rules based on tool arguments, user context, and more.

**Key Concepts:**
- **Tool Configuration**: Enable/disable tools and assign approval policies
- **Approval Policies** (Open-Core + Proprietary): Define approval requirements, approvers, timeouts, and notification channels
- **Conditional Approval** (Proprietary): Use CEL expressions to require approval only when specific conditions are met
- **Multi-Channel Notifications**: Email (open-core), mobile push, Slack, Mattermost, webhooks (proprietary)
- **Team-Based Approvals** (Proprietary): Assign approval rights to teams and require quorum
- **Escalation** (Proprietary): Automatically escalate to managers when approval times out

**Example: Conditional approval for high-value operations**

1. **Create an Approval Policy:**
   ```bash
   curl -X POST "https://YOUR_PRELOOP_AI_URL/api/v1/approval-policies" \
   -H "Authorization: Bearer YOUR_API_KEY" \
   -H "Content-Type: application/json" \
   -d '{
     "name": "Critical Operations",
     "description": "Require approval for critical issue operations",
     "is_default": false,
     "approver_user_ids": ["user-id-1", "user-id-2"],
     "approver_team_ids": ["team-id-1"],
     "approvals_required": 1,
     "timeout_seconds": 600,
     "notification_channels": ["email", "mobile_push", "slack"],
     "channel_configs": {
       "slack_webhook_url": "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
     }
   }'
   ```

2. **Configure tool with conditional approval:**
   ```bash
   curl -X POST "https://YOUR_PRELOOP_AI_URL/api/v1/tool-configurations" \
   -H "Authorization: Bearer YOUR_API_KEY" \
   -H "Content-Type: application/json" \
   -d '{
     "tool_name": "update_issue",
     "tool_source": "preloop_ai_builtin",
     "is_enabled": true,
     "approval_policy_id": "<policy_id_from_step_1>",
     "conditions": [
       {
         "condition_type": "argument",
         "condition_expression": "args.priority == \"critical\" || args.status == \"closed\"",
         "is_enabled": true
       }
     ]
   }'
   ```

   This configuration requires approval only when:
   - Setting an issue's priority to "critical", OR
   - Changing an issue's status to "closed"

3. **Mobile Device Registration:**
   - Users can register mobile devices via QR code from notification preferences
   - QR codes use Universal Links (iOS) and App Links (Android) for seamless setup
   - Mobile apps receive push notifications for approval requests
   - One-tap approve/decline directly from notifications

4. **When a tool call requires approval:**
   - Tool arguments are evaluated against CEL conditions
   - If conditions match, an approval request is created
   - Notifications sent to configured channels (email, mobile push, Slack, etc.)
   - Request waits for approval (up to timeout, with optional escalation)
   - If approved, tool executes; if declined/timed out, error is returned

**CEL Expression Examples:**
```cel
# Require approval for amounts over $1000
args.amount > 1000

# Require approval for production environments
args.environment == "production" || args.environment == "prod"

# Require approval for specific projects
args.project_id in ["proj-123", "proj-456"]

# Complex conditions
(args.priority == "critical" && args.assignee == null) || args.delete_data == true
```

For detailed setup instructions, see:
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture and approval flow

## Testing

Preloop AI uses pytest for unit and integration testing. The test suite covers API endpoints, database models, and tracker integrations.

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

## Contributing

Contributions are welcome! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on how to get started.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

The core of Preloop AI is open source software licensed under the [Apache License 2.0](LICENSE).

The proprietary plugins of Preloop AI are Copyright (c) 2025 Spacecode AI Inc. All rights reserved.
