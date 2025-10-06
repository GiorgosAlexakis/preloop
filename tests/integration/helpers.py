"""
Common helper functions and fixtures for integration tests.
"""

import asyncio
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
def create_mcp_client(base_url: str, api_key: str):
    """
    Create an MCP test client.

    Args:
        base_url: SpaceBridge base URL
        api_key: API key for authentication

    Returns:
        MCPTestClient instance (use as async context manager)
    """
    from tests.integration.mcp_client import MCPTestClient

    return MCPTestClient(base_url, api_key)


def run_mcp_test(base_url: str, api_key: str, test_func):
    """
    Run an async MCP test from a synchronous context.

    Args:
        base_url: SpaceBridge base URL
        api_key: API key for authentication
        test_func: Async function that receives an MCPTestClient and performs tests

    Returns:
        Whatever test_func returns

    Example:
        async def my_test(mcp_client):
            result = await mcp_client.create_issue(...)
            return result

        result = run_mcp_test(url, key, my_test)
    """

    async def _wrapper():
        async with create_mcp_client(base_url, api_key) as client:
            return await test_func(client)

    return asyncio.run(_wrapper())


# Legacy CLI-based MCP functions have been removed.
# Use create_mcp_client() and run_mcp_test() for direct,
# fast MCP testing without spawning Claude CLI processes.
