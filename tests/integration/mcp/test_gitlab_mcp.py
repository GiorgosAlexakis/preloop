"""
MCP integration test for GitLab tracker.

This test verifies the complete end-to-end flow using Claude MCP tools:
1. Create issue via MCP create_issue
2. Search for issue via MCP search
3. Get issue details via MCP get_issue
4. Update issue via MCP update_issue
5. Verify updates propagated to GitLab

Environment Variables Required:
- SPACEBRIDGE_TEST_URL: SpaceBridge instance URL
- SPACEBRIDGE_TEST_API_KEY: API key for SpaceBridge
- GITLAB_URL: GitLab instance URL (e.g., https://gitlab.com)
- GITLAB_API_KEY: GitLab personal access token
- GITLAB_TEST_PROJECT: Test project in format "group/project"

Usage:
    pytest tests/integration/mcp/test_gitlab_mcp.py -v -s
"""

import os
import time
import uuid
from urllib.parse import quote

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
GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.com").rstrip("/")
GITLAB_API_KEY = os.getenv("GITLAB_API_KEY", "")
GITLAB_TEST_PROJECT = os.getenv("GITLAB_TEST_PROJECT", "")  # e.g., "group/project"

# Test identifier
TEST_RUN_ID = f"mcp_test_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def gitlab_client():
    """Create GitLab API client."""
    if not GITLAB_API_KEY:
        pytest.skip("GITLAB_API_KEY required")

    headers = {"PRIVATE-TOKEN": GITLAB_API_KEY}
    with httpx.Client(base_url=f"{GITLAB_URL}/api/v4", headers=headers) as client:
        yield client


@pytest.mark.integration
@pytest.mark.mcp
@pytest.mark.skipif(
    not all(
        [SPACEBRIDGE_URL, SPACEBRIDGE_API_KEY, GITLAB_API_KEY, GITLAB_TEST_PROJECT]
    ),
    reason="SPACEBRIDGE_TEST_URL, SPACEBRIDGE_TEST_API_KEY, GITLAB_API_KEY, and GITLAB_TEST_PROJECT required",
)
def test_gitlab_mcp_integration(gitlab_client):
    """
    Complete MCP integration test for GitLab tracker.

    This test:
    - Sets up Claude MCP server connection
    - Creates an issue via MCP
    - Searches for the issue
    - Gets issue details
    - Updates the issue
    - Verifies updates in GitLab
    - Cleans up
    """
    print("\n" + "=" * 80)
    print("GITLAB MCP INTEGRATION TEST")
    print("=" * 80)

    created_issue_id = None
    created_issue_iid = None

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
            GITLAB_TEST_PROJECT,
            issue_title,
            issue_description,
            timeout=60,
        )
        print(f"✓ Created issue via MCP: {created_issue_id}")

        # Extract issue IID from the created issue ID
        # GitLab returns issues in format "group/project#123"
        if "#" in created_issue_id:
            created_issue_iid = created_issue_id.split("#")[1]
        else:
            created_issue_iid = created_issue_id

        # Step 3: Wait for indexing and search for issue
        print("\n" + "=" * 80)
        print("STEP 3: Search for Issue via MCP")
        print("=" * 80)

        time.sleep(10)  # Give time for indexing
        search_results = mcp_search_issue(
            "spacebridge", issue_title, project=GITLAB_TEST_PROJECT, limit=10
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

        # Step 6: Verify update in GitLab
        print("\n" + "=" * 80)
        print("STEP 6: Verify Update in GitLab")
        print("=" * 80)

        time.sleep(5)  # Give time for sync
        encoded_project = quote(GITLAB_TEST_PROJECT, safe="")
        gitlab_issue_response = gitlab_client.get(
            f"/projects/{encoded_project}/issues/{created_issue_iid}"
        )
        gitlab_issue_response.raise_for_status()
        gitlab_issue = gitlab_issue_response.json()

        assert gitlab_issue["title"] == updated_title, (
            f"Title not synced to GitLab: got '{gitlab_issue['title']}', "
            f"expected '{updated_title}'"
        )
        print("✓ Update propagated to GitLab")
        print("\n✅ GitLab MCP integration test PASSED")

    finally:
        # Cleanup
        print("\n" + "=" * 80)
        print("CLEANUP")
        print("=" * 80)

        # Delete created issue from GitLab
        if created_issue_iid:
            try:
                encoded_project = quote(GITLAB_TEST_PROJECT, safe="")
                gitlab_client.delete(
                    f"/projects/{encoded_project}/issues/{created_issue_iid}"
                )
                print(f"✓ Deleted GitLab issue #{created_issue_iid}")
            except Exception as e:
                print(f"✗ Failed to delete GitLab issue: {e}")

        cleanup_claude_mcp_server()
