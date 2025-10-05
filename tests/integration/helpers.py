"""
Common helper functions and fixtures for integration tests.
"""

import subprocess
import time
from typing import Any, Dict
from urllib.parse import quote

import httpx


def run_command(command: list, input_data: str = None, timeout: int = 30) -> str:
    """Runs a command and returns its stdout, raising an error on failure."""
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        input=input_data,
        check=True,
        timeout=timeout,
    )
    return process.stdout.strip()


def wait_for_issue(
    client: httpx.Client, issue_key: str, timeout: int
) -> Dict[str, Any]:
    """Poll SpaceBridge until issue is available or timeout."""
    print(f"⏳ Waiting for issue {issue_key} to be indexed (timeout: {timeout}s)...")
    start_time = time.time()

    # URL-encode the issue_key to handle special characters like #
    encoded_issue_key = quote(issue_key, safe="")

    while time.time() - start_time < timeout:
        try:
            response = client.get(f"/api/v1/issues/{encoded_issue_key}")
            if response.status_code == 200:
                elapsed = int(time.time() - start_time)
                print(f"✓ Issue {issue_key} is now available (took {elapsed}s)")
                return response.json()
        except Exception as e:
            print(f"  ... polling ({int(time.time() - start_time)}s): {e}")

        time.sleep(5)  # Poll every 5 seconds

    raise TimeoutError(f"Issue {issue_key} not available after {timeout}s")


def wait_for_issue_update(
    client: httpx.Client, issue_key: str, expected_title: str, timeout: int
) -> Dict[str, Any]:
    """Poll SpaceBridge until issue title matches expected value or timeout."""
    print(
        f"⏳ Waiting for issue {issue_key} to update via webhook (timeout: {timeout}s)..."
    )
    start_time = time.time()

    # URL-encode the issue_key to handle special characters like #
    encoded_issue_key = quote(issue_key, safe="")

    while time.time() - start_time < timeout:
        try:
            response = client.get(f"/api/v1/issues/{encoded_issue_key}")
            if response.status_code == 200:
                issue_data = response.json()
                if issue_data.get("title") == expected_title:
                    elapsed = int(time.time() - start_time)
                    print(f"✓ Issue {issue_key} updated via webhook (took {elapsed}s)")
                    return issue_data
                else:
                    print(
                        f"  ... title mismatch: got '{issue_data.get('title')}', expected '{expected_title}'"
                    )
        except Exception as e:
            print(f"  ... polling ({int(time.time() - start_time)}s): {e}")

        time.sleep(2)  # Poll every 2 seconds for webhook updates

    raise TimeoutError(
        f"Issue {issue_key} did not update to expected title after {timeout}s"
    )


# MCP Helper Functions
def setup_claude_mcp_server(
    base_url: str, api_key: str, server_name: str = "spacebridge"
):
    """Add SpaceBridge as an MCP server in Claude Code."""
    print(f"\n⚙️  Setting up Claude Code MCP server '{server_name}'...")

    # Remove if it exists (cleanup from previous runs)
    try:
        run_command(["claude", "mcp", "remove", server_name])
        print(f"  Removed existing '{server_name}' server")
    except subprocess.CalledProcessError:
        pass  # Server doesn't exist, that's OK

    # Add the server
    run_command(
        [
            "claude",
            "mcp",
            "add",
            "--transport",
            "http",
            server_name,
            f"{base_url}/mcp/v1",
            "--header",
            f"Authorization: Bearer {api_key}",
        ]
    )
    print(f"✓ Added SpaceBridge MCP server: {server_name}")


def verify_mcp_server(server_name: str = "spacebridge"):
    """Verify that the SpaceBridge MCP server is connected."""
    print(f"\n🔍 Verifying MCP server '{server_name}' connection...")

    mcp_servers = run_command(["claude", "mcp", "list"])
    assert server_name in mcp_servers, f"MCP server '{server_name}' not found in list"
    assert "✓ Connected" in mcp_servers or "Connected" in mcp_servers, (
        f"MCP server '{server_name}' not connected"
    )

    print(f"✓ MCP server '{server_name}' is connected")
    return True


def verify_mcp_tools(server_name: str = "spacebridge"):
    """Verify that SpaceBridge MCP tools are available."""
    print(f"\n🔍 Verifying MCP tools for server '{server_name}'...")

    # List available tools
    tools_output = run_command(["claude", "mcp", "tools", server_name])

    expected_tools = ["get_issue", "create_issue", "update_issue", "search"]
    for tool in expected_tools:
        assert tool in tools_output, f"MCP tool '{tool}' not found"
        print(f"  ✓ Found tool: {tool}")

    print("✓ All required MCP tools are available")
    return True


def cleanup_claude_mcp_server(server_name: str = "spacebridge"):
    """Remove SpaceBridge MCP server from Claude Code."""
    print(f"\n🧹 Cleaning up Claude Code MCP server '{server_name}'...")
    try:
        run_command(["claude", "mcp", "remove", server_name])
        print(f"✓ Removed MCP server: {server_name}")
    except subprocess.CalledProcessError as e:
        print(f"  Warning: Could not remove MCP server: {e}")


def mcp_create_issue(
    server_name: str, project: str, title: str, description: str, timeout: int = 30
) -> str:
    """Create an issue via MCP and return the issue key."""
    print(f"\n📝 Creating issue via MCP: {title}")

    # Use claude mcp call to invoke create_issue tool
    result = run_command(
        [
            "claude",
            "mcp",
            "call",
            server_name,
            "create_issue",
            "--arg",
            f"project={project}",
            "--arg",
            f"title={title}",
            "--arg",
            f"description={description}",
        ],
        timeout=timeout,
    )

    # Parse the result to extract the issue ID/key
    # The result should be JSON with issue_id
    import json

    result_data = json.loads(result)
    issue_id = result_data.get("issue_id") or result_data.get("id")

    print(f"✓ Created issue via MCP: {issue_id}")
    return issue_id


def mcp_search_issue(
    server_name: str,
    query: str,
    project: str = None,
    limit: int = 10,
    timeout: int = 30,
) -> list:
    """Search for issues via MCP."""
    print(f"\n🔍 Searching via MCP: {query}")

    cmd = [
        "claude",
        "mcp",
        "call",
        server_name,
        "search",
        "--arg",
        f"query={query}",
        "--arg",
        f"limit={limit}",
    ]

    if project:
        cmd.extend(["--arg", f"project={project}"])

    result = run_command(cmd, timeout=timeout)

    # Parse the result
    import json

    result_data = json.loads(result)
    results = result_data.get("results", [])

    print(f"✓ Found {len(results)} issues via MCP")
    return results


def mcp_get_issue(server_name: str, issue: str, timeout: int = 30) -> Dict[str, Any]:
    """Get issue details via MCP."""
    print(f"\n📄 Getting issue via MCP: {issue}")

    result = run_command(
        [
            "claude",
            "mcp",
            "call",
            server_name,
            "get_issue",
            "--arg",
            f"issue={issue}",
        ],
        timeout=timeout,
    )

    # Parse the result
    import json

    issue_data = json.loads(result)

    print(f"✓ Retrieved issue via MCP: {issue_data.get('key', issue)}")
    return issue_data


def mcp_update_issue(
    server_name: str,
    issue: str,
    title: str = None,
    description: str = None,
    status: str = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Update an issue via MCP."""
    print(f"\n✏️  Updating issue via MCP: {issue}")

    cmd = [
        "claude",
        "mcp",
        "call",
        server_name,
        "update_issue",
        "--arg",
        f"issue={issue}",
    ]

    if title:
        cmd.extend(["--arg", f"title={title}"])
    if description:
        cmd.extend(["--arg", f"description={description}"])
    if status:
        cmd.extend(["--arg", f"status={status}"])

    result = run_command(cmd, timeout=timeout)

    # Parse the result
    import json

    issue_data = json.loads(result)

    print(f"✓ Updated issue via MCP: {issue_data.get('key', issue)}")
    return issue_data
