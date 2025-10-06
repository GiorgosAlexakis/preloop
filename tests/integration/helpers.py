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


def cleanup_claude_mcp_server(server_name: str = "spacebridge"):
    """Remove SpaceBridge MCP server from Claude Code."""
    print(f"\n🧹 Cleaning up Claude Code MCP server '{server_name}'...")
    try:
        run_command(["claude", "mcp", "remove", server_name])
        print(f"✓ Removed MCP server: {server_name}")
    except subprocess.CalledProcessError as e:
        print(f"  Warning: Could not remove MCP server: {e}")


def mcp_create_issue(
    server_name: str, project: str, title: str, description: str, timeout: int = 60
) -> str:
    """
    Create an issue via MCP.

    Returns the text output from Claude (not parsed JSON).
    Tests should verify the creation by checking the tracker directly or
    checking that key information appears in the output.
    """
    print(f"\n📝 Creating issue via MCP: {title}")

    prompt = f"create issue in project {project} with title '{title}' and description '{description}'"
    result = run_command(
        [
            "claude",
            "-p",
            prompt,
            "--allowedTools",
            f"mcp__{server_name}__create_issue",
        ],
        timeout=timeout,
    )

    print(f"✓ MCP create_issue completed, output length: {len(result)} chars")
    return result


def mcp_search_issue(
    server_name: str,
    query: str,
    project: str = None,
    limit: int = 10,
    timeout: int = 60,
) -> str:
    """
    Search for issues via MCP.

    Returns the text output from Claude (not parsed JSON).
    Tests should verify that the expected issue key appears in the output.
    """
    print(f"\n🔍 Searching via MCP: {query}")

    prompt = f"search for issues with query '{query}' with limit {limit}"
    if project:
        prompt += f" in project {project}"

    result = run_command(
        [
            "claude",
            "-p",
            prompt,
            "--allowedTools",
            f"mcp__{server_name}__search",
        ],
        timeout=timeout,
    )

    print(f"✓ MCP search completed, output length: {len(result)} chars")
    return result


def mcp_get_issue(server_name: str, issue: str, timeout: int = 60) -> str:
    """
    Get issue details via MCP.

    Returns the text output from Claude (not parsed JSON).
    Tests should verify that key information appears in the output.
    """
    print(f"\n📄 Getting issue via MCP: {issue}")

    prompt = f"get issue {issue}"
    result = run_command(
        [
            "claude",
            "-p",
            prompt,
            "--allowedTools",
            f"mcp__{server_name}__get_issue",
        ],
        timeout=timeout,
    )

    print(f"✓ MCP get_issue completed, output length: {len(result)} chars")
    return result


def mcp_update_issue(
    server_name: str,
    issue: str,
    title: str = None,
    description: str = None,
    status: str = None,
    timeout: int = 60,
) -> str:
    """
    Update an issue via MCP.

    Returns the text output from Claude (not parsed JSON).
    Tests should verify the update by checking the tracker directly.
    """
    print(f"\n✏️  Updating issue via MCP: {issue}")

    prompt = f"update issue {issue}"
    if title:
        prompt += f" with title '{title}'"
    if description:
        prompt += f" and description '{description}'"
    if status:
        prompt += f" and status '{status}'"

    result = run_command(
        [
            "claude",
            "-p",
            prompt,
            "--allowedTools",
            f"mcp__{server_name}__update_issue",
        ],
        timeout=timeout,
    )

    print(f"✓ MCP update_issue completed, output length: {len(result)} chars")
    return result
