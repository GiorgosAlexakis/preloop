# SpaceBridge

![SpaceBridge Logo](assets/logo.webp)

## Overview

SpaceBridge.io drives your product using AI. It ingests issues, comments, documentation and (optionally) code from your issue tracker. It detects duplication and overlap of issues, evaluates compliance metrics and provides suggestions with the most impactful actions to improve your issue tracker.

## Key Features

- Continuous ingestion of issues, comments, projects, and organizations from your issue tracker
- Vector-based similarity search across issue trackers and projects
- Intelligent detection of duplication and overlap of issues
- Evaluation of compliance metrics and recommendations for improvement
- Event Driven Agentic Flows triggered by issue tracker events, with real-time monitoring.
- A comprehensive Web UI for managing trackers, projects, and flows.
- MCP server & RESTful API.

## Supported Issue Trackers

- Jira Cloud and Server
- GitHub Issues
- GitLab Issues
- (More to be added in future releases, including Azure DevOps and Linear)

## Architecture

SpaceBridge is designed with a modular architecture:

1.  **SpaceBridge** (this repository): The main RESTful HTTP API server that provides access to issue tracking systems and vector search capabilities.
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
git clone https://github.com/spacecode/spacebridge.git
cd spacebridge

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
git clone https://github.com/spacecode/spacebridge.git
cd spacebridge

# Run with Docker Compose
docker-compose up
```

### Kubernetes Setup

SpaceBridge can be deployed to Kubernetes using the provided Helm chart:

```bash
# Add the SpaceCode Helm repository (if available)
# helm repo add spacecode https://charts.spacecode.ai
# helm repo update

# Install from the local chart
helm install spacebridge ./helm/spacebridge

# Or install with custom values
helm install spacebridge ./helm/spacebridge --values custom-values.yaml
```

For more details about the Helm chart, see the [chart README](./helm/spacebridge/README.md).

## Usage

### Starting the Server

1.  **Set Environment Variables:**
    Ensure you have a `.env` file configured with the necessary environment variables (see `.env.example`). Key variables include database connection details, API keys, etc.

2.  **Start SpaceBridge API:**
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

SpaceBridge provides a RESTful HTTP API for interacting with issue tracking systems:

```python
import requests
import json

# Base URL for the SpaceBridge API
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

SpaceBridge provides a RESTful API with the following key endpoints:

### Authentication
- `POST /api/v1/auth/token` - Get authentication token
- `POST /api/v1/auth/refresh` - Refresh authentication token

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

### Using MCP Tools via API

The SpaceBridge API now includes integrated MCP tool endpoints, allowing any HTTP-based MCP client to connect directly. This is the recommended way to automate issue management workflows.

**Authentication:** All MCP endpoints use the same Bearer Token authentication as the rest of the API.

**Connecting with Claude Code:**

You can connect Claude Code directly to your SpaceBridge instance using the `claude mcp add` command.

1.  **Get your SpaceBridge API Key:** You can find or create an API key in your SpaceBridge user settings.
2.  **Add the MCP Server:** Run the following command, replacing `YOUR_SPACEBRIDGE_URL` and `YOUR_API_KEY` with your details.

    ```bash
    claude mcp add \
      --transport http \
      --header "Authorization: Bearer YOUR_API_KEY" \
      spacebridge \
      https://YOUR_SPACEBRIDGE_URL/api/v1/mcp
    ```

    - `--transport http`: Specifies that the server uses the HTTP transport.
    - `--header "Authorization: Bearer YOUR_API_KEY"`: Provides the necessary authentication header for all requests.
    - `spacebridge`: This is the name you will use to refer to the server (e.g., `@spacebridge get_issue ...`).
    - `https://YOUR_SPACEBRIDGE_URL/api/v1/mcp`: This is the base URL for the SpaceBridge MCP endpoints.

**Example Workflow (using `curl`):**

If you are not using an MCP client and want to interact with the tool endpoints directly, you can use any HTTP client like `curl`.

1.  **Create an Issue:**
    ```bash
    curl -X POST "https://YOUR_SPACEBRIDGE_URL/api/v1/mcp/create_issue" \
    -H "Authorization: Bearer YOUR_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "project": "your-org/your-project",
      "title": "New Feature Request",
      "description": "Add a dark mode to the dashboard."
    }'
    ```

## Testing

SpaceBridge uses pytest for unit and integration testing. The test suite covers API endpoints, database models, and tracker integrations.

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

Copyright (c) 2025 SpaceCode. All rights reserved.
