"""
MCP integration test for GitHub tracker.

This test verifies the complete end-to-end flow using Claude MCP tools:
1. Create issue via MCP create_issue
2. Search for issue via MCP search
3. Get issue details via MCP get_issue
4. Update issue via MCP update_issue
5. Verify updates propagated to GitHub

Environment Variables Required:
- SPACEBRIDGE_TEST_URL: SpaceBridge instance URL
- SPACEBRIDGE_TEST_API_KEY: API key for SpaceBridge
- GITHUB_API_KEY: GitHub personal access token
- GITHUB_TEST_REPO: Test repository in format "owner/repo"

Usage:
    pytest tests/integration/mcp/test_github_mcp.py -v -s
"""

import os
import time
import uuid

import httpx
import pytest

from tests.integration.helpers import (
    cleanup_claude_mcp_server,
    mcp_create_issue,
    mcp_get_issue,
    mcp_search_issue,
    mcp_update_issue,
    setup_claude_mcp_server,
    verify_mcp_server,
    verify_mcp_tools,
)

# Test configuration
SPACEBRIDGE_URL = os.getenv("SPACEBRIDGE_TEST_URL", "").rstrip("/")
SPACEBRIDGE_API_KEY = os.getenv("SPACEBRIDGE_TEST_API_KEY", "")
GITHUB_API_KEY = os.getenv("GITHUB_API_KEY", "")
GITHUB_TEST_REPO = os.getenv("GITHUB_TEST_REPO", "")  # e.g., "owner/repo"

# Test identifier
TEST_RUN_ID = f"mcp_test_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def github_client():
    """Create GitHub API client."""
    if not GITHUB_API_KEY:
        pytest.skip("GITHUB_API_KEY required")

    headers = {
        "Authorization": f"token {GITHUB_API_KEY}",
        "Accept": "application/vnd.github.v3+json",
    }
    with httpx.Client(base_url="https://api.github.com", headers=headers) as client:
        yield client


@pytest.mark.integration
@pytest.mark.mcp
@pytest.mark.skipif(
    not all([SPACEBRIDGE_URL, SPACEBRIDGE_API_KEY, GITHUB_API_KEY, GITHUB_TEST_REPO]),
    reason="SPACEBRIDGE_TEST_URL, SPACEBRIDGE_TEST_API_KEY, GITHUB_API_KEY, and GITHUB_TEST_REPO required",
)
def test_github_mcp_integration(github_client):
    """
    Complete MCP integration test for GitHub tracker.

    This test:
    - Sets up Claude MCP server connection
    - Creates an issue via MCP
    - Searches for the issue
    - Gets issue details
    - Updates the issue
    - Verifies updates in GitHub
    - Cleans up
    """
    print("\n" + "=" * 80)
    print("GITHUB MCP INTEGRATION TEST")
    print("=" * 80)

    created_issue_id = None
    created_issue_number = None

    try:
        # Step 1: Setup MCP server
        print("\n" + "=" * 80)
        print("STEP 1: Setup Claude MCP Server")
        print("=" * 80)

        setup_claude_mcp_server(SPACEBRIDGE_URL, SPACEBRIDGE_API_KEY)
        verify_mcp_server()
        verify_mcp_tools()

        # Step 2: Create issue via MCP
        print("\n" + "=" * 80)
        print("STEP 2: Create Issue via MCP")
        print("=" * 80)

        issue_title = f"MCP Test Issue {TEST_RUN_ID}"
        issue_description = f"This is a test issue created via MCP at {time.time()}"

        created_issue_id = mcp_create_issue(
            "spacebridge",
            GITHUB_TEST_REPO,
            issue_title,
            issue_description,
            timeout=60,
        )
        print(f"✓ Created issue via MCP: {created_issue_id}")

        # Extract issue number from the created issue ID
        # GitHub returns issues in format "owner/repo#123"
        if "#" in created_issue_id:
            created_issue_number = created_issue_id.split("#")[1]
        else:
            created_issue_number = created_issue_id

        # Step 3: Wait for indexing and search for issue
        print("\n" + "=" * 80)
        print("STEP 3: Search for Issue via MCP")
        print("=" * 80)

        time.sleep(10)  # Give time for indexing
        search_results = mcp_search_issue(
            "spacebridge", issue_title, project=GITHUB_TEST_REPO, limit=10
        )

        assert len(search_results) > 0, "Issue not found in search results"
        assert any(
            TEST_RUN_ID in result.get("title", "") for result in search_results
        ), "Test issue not in search results"
        print(f"✓ Found issue in search results: {len(search_results)} results")

        # Step 4: Get issue details via MCP
        print("\n" + "=" * 80)
        print("STEP 4: Get Issue Details via MCP")
        print("=" * 80)

        issue_data = mcp_get_issue("spacebridge", created_issue_id)

        assert issue_data.get("title") == issue_title
        assert TEST_RUN_ID in issue_data.get("description", "")
        print(f"✓ Retrieved issue details: {issue_data.get('key')}")

        # Step 5: Update issue via MCP
        print("\n" + "=" * 80)
        print("STEP 5: Update Issue via MCP")
        print("=" * 80)

        updated_title = f"{issue_title} (Updated)"
        updated_description = f"{issue_description}\n\nUpdated via MCP"

        updated_issue = mcp_update_issue(
            "spacebridge",
            created_issue_id,
            title=updated_title,
            description=updated_description,
        )

        assert updated_issue.get("title") == updated_title
        print("✓ Updated issue via MCP")

        # Step 6: Verify update in GitHub
        print("\n" + "=" * 80)
        print("STEP 6: Verify Update in GitHub")
        print("=" * 80)

        time.sleep(5)  # Give time for sync
        github_issue_response = github_client.get(
            f"/repos/{GITHUB_TEST_REPO}/issues/{created_issue_number}"
        )
        github_issue_response.raise_for_status()
        github_issue = github_issue_response.json()

        assert github_issue["title"] == updated_title, (
            f"Title not synced to GitHub: got '{github_issue['title']}', "
            f"expected '{updated_title}'"
        )
        print("✓ Update propagated to GitHub")
        print("\n✅ GitHub MCP integration test PASSED")

    finally:
        # Cleanup
        print("\n" + "=" * 80)
        print("CLEANUP")
        print("=" * 80)

        # Delete created issue from GitHub
        if created_issue_number:
            try:
                # GitHub doesn't have a delete issue API, so we close it instead
                github_client.patch(
                    f"/repos/{GITHUB_TEST_REPO}/issues/{created_issue_number}",
                    json={"state": "closed"},
                )
                print(f"✓ Closed GitHub issue #{created_issue_number}")
            except Exception as e:
                print(f"✗ Failed to close GitHub issue: {e}")

        cleanup_claude_mcp_server()
