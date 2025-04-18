# SpaceBridge Documentation

## Overview

SpaceBridge is an open-source Model Context Protocol (MCP) server that provides a unified API for interacting with multiple issue tracking systems (GitHub, GitLab, Jira) from AI assistants. It functions as a bridge between AI agents and issue trackers by:

1. **Standardizing issue data across platforms** - converting between different trackers' schemas
2. **Providing semantic search and similarity matching** - finding related issues through vector embedding
3. **Exposing a consistent interface** - through both direct REST API and MCP-compliant stdio transport

Developed specifically for AI agent integration, SpaceBridge lets AI assistants create, update, and search for issues across multiple tracking systems without requiring separate integrations for each platform.


## Supported Issue Trackers

- GitHub Issues
- GitLab Issues
- Jira Cloud and Server (coming soon)
- Linear (coming soon)

## Architecture

```mermaid
graph LR
    MCP Clients (Claude Code) --> SpaceBridge MCP Server
    SpaceBridge MCP Server --> SpaceBridge REST API
    SpaceBridge REST API --> Issue Trackers (Jira/GitHub/GitLab)
```

### SpaceBridge-MCP

SpaceBridge-MCP acts as a bridge between MCP clients and the SpaceBridge REST API. When an MCP client invokes a tool, SpaceBridge-MCP:

- Receives the tool invocation via stdio
- Validates the parameters
- Translates the request to an HTTP call to the SpaceBridge REST API
- Returns the result back to the MCP client

### SpaceBridge REST API

The SpaceBridge REST API provides a set of endpoints for interacting with issue trackers. It supports operations such as:

- Creating new issues
- Updating existing issues
- Searching for issues
- Managing issue assignments
- Adding comments to issues

## Getting Started

### Prerequisites

- Python 3.9+
- pip (Python package installer)
- Access to a SpaceBridge instance and API key.
- OpenAI API Key (for the `create_issue` tool's duplicate check).

### Installation using pip

1.  Install the package:
    ```bash
    pip install spacebridge-mcp
    ```

### Installation from source

1.  Clone the repository:
    ```bash
    git clone <repository-url>
    cd spacebridge-mcp
    ```
2.  Create and activate a virtual environment (recommended):
    ```bash
    # Use .venv as requested by user
    python -m venv .venv
    source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
    ```
3.  Install the package in editable mode, including development dependencies (for testing):
    ```bash
    # Use the specific python from your virtual env if 'pip' isn't found directly
    .venv/bin/python -m pip install -e ".[dev]"
    # Or if 'pip' is correctly on PATH for the venv:
    # pip install -e ".[dev]"
    ```
    *Note: This installs the package such that changes to the source code are immediately reflected without reinstalling. Including `[dev]` installs packages needed for running tests, like `pytest` and `respx`.*

### Configuration

The server requires the following configuration values:

*   **SpaceBridge API URL:** The base URL for your SpaceBridge API instance (e.g., `https://your-spacebridge.com/api/v1`).
*   **SpaceBridge API Key:** Your API key for authenticating with SpaceBridge.
*   **OpenAI API Key:** Your API key for OpenAI, used by the `create_issue` tool for duplicate checking.

These values can be provided in three ways, with the following order of precedence (highest first):

1.  **Command-line Arguments:** Pass arguments when running the server:
    ```bash
    spacebridge-mcp-server \
      --spacebridge-api-url "YOUR_URL" \
      --spacebridge-api-key "YOUR_SB_KEY" \
      --openai-api-key "YOUR_OPENAI_KEY"
    ```
    *(Use `spacebridge-mcp-server --help` to see all available arguments.)*

2.  **Environment Variables:** Set standard environment variables:
    ```bash
    export SPACEBRIDGE_API_URL="YOUR_URL"
    export SPACEBRIDGE_API_KEY="YOUR_SB_KEY"
    export OPENAI_API_KEY="YOUR_OPENAI_KEY"
    # Then run:
    spacebridge-mcp-server
    ```

3.  **.env File:** Create a file named `.env` in the directory where you run the server:
    ```dotenv
    # .env file content
    SPACEBRIDGE_API_URL="YOUR_URL"
    SPACEBRIDGE_API_KEY="YOUR_SB_KEY"
    OPENAI_API_KEY="YOUR_OPENAI_KEY"
    ```
    The server will automatically load values from this file if it exists. Values from environment variables or command-line arguments will override those in the `.env` file.

**Note:** When configuring MCP clients like Claude code (see "Connecting MCP Clients" section), passing credentials via the client's `--env` flags effectively sets them as environment variables for the server process.

### Running the Server

Once installed and configured, you can run the server using the command defined in `pyproject.toml`:

```bash
spacebridge-mcp-server
```

The server will start listening for MCP connections via standard input/output (stdio) by default.

## Connecting MCP Clients

This server uses standard input/output (stdio) for communication. You need to configure your MCP client (e.g., Claude code, Windsurf, Cursor) to launch the `spacebridge-mcp-server` command and pass the required environment variables. The `spacebridge-mcp-server` command should be available in your environment's path.

### Configuring Claude Code with SpaceBridge

```bash
claude mcp add spacebridge \
  /full/path/to/your/spacebridge-mcp-server \
  --scope user \
  --env SPACEBRIDGE_API_URL="https://spacebridge.com/api" \
  --env SPACEBRIDGE_API_KEY="your-spacebridge-api-key" \
  --env OPENAI_API_KEY="your-openai-api-key"
```

`--scope user` makes the server available across all your projects in Claude code. Use `--scope project` to limit it to the current project.

### Configuring Cursor with SpaceBridge

#### Method 1: Using the Cursor UI

1. Open Cursor and navigate to **Settings** > **Model Context Protocol**
2. Click **Add MCP Server**
3. Select **Add stdio Server**
4. Enter the following information:
   - **Name**: `SpaceBridge`
   - **Command**: Full path to `spacebridge-mcp-server` (see "Find Server Path" above)
   - **Environment Variables**: Add the following key-value pairs:
     - `SPACEBRIDGE_API_URL`: Your SpaceBridge API URL
     - `SPACEBRIDGE_API_KEY`: Your SpaceBridge API key
     - `OPENAI_API_KEY`: Your OpenAI API key for similarity search

#### Method 2: Editing the Configuration File

1. **Project-specific configuration** (only available in this project):
   Create a file at `.cursor/mcp.json` in your project directory with:

   ```json
   {
     "mcpServers": {
       "spacebridge": {
         "command": "/full/path/to/spacebridge-mcp-server",
         "args": [],
         "env": {
           "SPACEBRIDGE_API_URL": "https://spacebridge.com/api",
           "SPACEBRIDGE_API_KEY": "your-spacebridge-api-key",
           "OPENAI_API_KEY": "your-openai-api-key"
         }
       }
     }
   }
   ```

2. **Global configuration** (available in all projects):
   Create a file at `~/.cursor/mcp.json` in your home directory with the same structure as above.

Once configured, Cursor's AI assistant will automatically detect and use available SpaceBridge tools when relevant to your task. You can also explicitly tell the assistant to use SpaceBridge tools by mentioning them in your prompts.

### Configuring Windsurf with SpaceBridge

Windsurf uses a JSON configuration file to manage MCP servers. Here's how to set up SpaceBridge with Windsurf:

#### Editing the Configuration File

1. Create or edit the Windsurf MCP configuration file at `~/.codeium/windsurf/mcp_config.json` with the following content:

   ```json
   {
     "mcpServers": {
       "spacebridge": {
         "command": "/full/path/to/spacebridge-mcp-server",
         "args": [],
         "env": {
           "SPACEBRIDGE_API_URL": "https://spacebridge.io/api",
           "SPACEBRIDGE_API_KEY": "your-spacebridge-api-key",
           "OPENAI_API_KEY": "your-openai-api-key"
         }
       }
     }
   }
   ```

The configuration file specifies:
- The path to the `spacebridge-mcp-server` executable
- Your SpaceBridge API URL and API key
- Your OpenAI API key for similarity search and duplicate detection

Once configured, Windsurf's AI assistant will automatically detect and use available SpaceBridge tools when relevant to your task. You can also explicitly tell the assistant to use SpaceBridge tools by mentioning them in your prompts.

### Using SpaceBridge

After configuration, you can use SpaceBridge features directly within your MCP-enabled IDE:

1. **Search for Issues**: Ask your IDE to search for issues related to your current task
2. **Create Issues**: Tell your IDE to create a new issue for a bug or feature request
3. **Link Code to Issues**: Ask your IDE to link your current code to relevant issues

### Usage Examples

- "Find issues related to authentication bugs"
- "Create a new issue for this login page crash"
- "Link this function to issue #123"
