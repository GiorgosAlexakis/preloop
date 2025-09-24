import os
import pytest
import subprocess

# Environment variables
BASE_URL = os.environ.get("SPACEBRIDGE_TEST_URL")
API_KEY = os.environ.get("SPACEBRIDGE_TEST_API_KEY")

# Configuration for the MCP client
MCP_CLIENT_CONFIG = {
    "servers": [
        {
            "name": "spacebridge_test",
            "transport": "http",
            "url": f"{BASE_URL}/mcp/v1",
            "headers": {"Authorization": f"Bearer {API_KEY}"},
        }
    ]
}


def run_command(command: list, input_data: str = None) -> str:
    """Runs a command and returns its stdout, raising an error on failure."""
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        input=input_data,
        check=True,  # Will raise CalledProcessError on non-zero exit codes
    )
    return process.stdout.strip()


@pytest.fixture(scope="module", autouse=True)
def setup_mcp_client():
    """Sets up the MCP client for integration tests."""
    if not BASE_URL or not API_KEY:
        pytest.fail("SPACEBRIDGE_TEST_URL or SPACEBRIDGE_TEST_API_KEY not set")

    # Add the SpaceBridge test instance to the MCP client
    run_command(
        [
            "claude",
            "mcp",
            "add",
            "--transport",
            "http",
            "spacebridge",
            f"{BASE_URL}/mcp/v1",
            "--header",
            f"Authorization: Bearer {API_KEY}",
        ]
    )

    yield

    # Teardown: remove the server configuration
    run_command(["claude", "mcp", "remove", "spacebridge"])


def test_mcp_tools_are_available(setup_mcp_client):
    """Verify that the SpaceBridge MCP tools are available via the client."""

    # List available MCP servers and verify that Spacebridge is connected
    mcp_servers = run_command(["claude", "mcp", "list"])

    assert "spacebridge" in mcp_servers
    assert "✓ Connected" in mcp_servers
