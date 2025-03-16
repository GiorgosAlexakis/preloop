# SpaceBridge

## Overview

SpaceBridge is a Model Context Protocol (MCP) server that serves as a unified interface between Spacecode's infrastructure and multiple issue tracking systems. It enables seamless searching, creation, and updating of issues across different platforms through a standardized protocol.

## Key Features

- Unified API for interacting with multiple issue tracking systems
- Vector-based semantic search across all integrated issue trackers
- Intelligent duplicate detection and issue management
- Automated assignment suggestions and effort estimation
- Cross-tracker issue dependency management
- Self-service organization and project configuration via MCP tools
- AI-friendly interfaces for both human and agent interaction

## Supported Issue Trackers

- Jira
- GitHub Issues
- GitLab Issues
- (More to be added in future releases)

## Installation

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- PGVector extension for PostgreSQL

### Setup

```bash
# Clone the repository
git clone https://github.com/spacecode/spacebridge.git
cd spacebridge

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Set up the database
python -m spacebridge.db.setup

# Configure your environment
cp .env.example .env
# Edit .env with your settings
```

## Usage

### Starting the Server

```bash
python -m spacebridge.server
```

### Using MCP Tools

SpaceBridge implements the Model Context Protocol, allowing for standardized interaction:

```python
from mcp.client import MCPClient

client = MCPClient("http://localhost:8000")

# Search for issues related to authentication
results = client.invoke("search_issues", {
    "organization": "spacecode",
    "project": "astrobot",
    "query": "authentication problems",
    "limit": 5
})

# Create a new issue
issue = client.invoke("create_issue", {
    "organization": "spacecode",
    "project": "astrobot",
    "title": "Improve login error messages",
    "description": "Current error messages are not clear enough...",
    "labels": ["enhancement", "authentication"]
})
```

## Contributing

Contributions are welcome! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on how to get started.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
