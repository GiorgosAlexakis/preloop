# SpaceBridge

![SpaceBridge Logo](assets/logo.webp)

## Overview

SpaceBridge is a RESTful API server that serves as a unified interface between Spacecode's infrastructure and multiple issue tracking systems. It enables seamless searching, creation, and updating of issues across different platforms through a standardized HTTP API.

## Key Features

- RESTful API for interacting with multiple issue tracking systems
- Vector-based similarity search across all integrated issue trackers
- Intelligent duplicate detection and issue management
- Automated assignment suggestions and effort estimation
- Self-service organization and project configuration
- AI-friendly interfaces for both human and agent interaction

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
4.  **SpaceBridge-MCP** (separate repository): A Model Context Protocol (MCP) server that uses stdio transport and serves as a bridge between MCP clients (like Claude Code) and the SpaceBridge API.

This structure allows:
- Clear separation of concerns between the API layer, data models, synchronization logic, and MCP integration.
- Independent development and versioning of the core components.
- Direct HTTP API access for applications that don't need MCP.

## Installation

### Prerequisites

- Python 3.10+
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

### For MCP Clients (Claude Code)

For MCP clients like Claude Code, use the companion [SpaceBridge-MCP](https://github.com/spacecode-ai/SpaceBridge-MCP) project, which provides MCP tools that communicate with SpaceBridge.

```bash
# Install SpaceBridge-MCP
pip install SpaceBridge-MCP

# Configure Claude Code to use SpaceBridge-MCP
claude mcp add SpaceBridge-MCP "python -m SpaceBridge-MCP.server"

# Set environment variables for SpaceBridge-MCP
export SPACEBRIDGE_URL="http://localhost:8000/api/v1"
export SPACEBRIDGE_API_KEY="your-api-key"

# List available tools in Claude Code
claude tools list

# Use SpaceBridge tools via Claude
claude "Search for issues related to authentication in the Astrobot project"
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

## Contributing

Contributions are welcome! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on how to get started.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
