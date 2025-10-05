"""
MCP integration test for Jira tracker.

This test verifies the complete end-to-end flow using Claude MCP tools:
1. Create issue via MCP create_issue
2. Search for issue via MCP search
3. Get issue details via MCP get_issue
4. Update issue via MCP update_issue
5. Verify updates propagated to Jira

Environment Variables Required:
- SPACEBRIDGE_TEST_URL: SpaceBridge instance URL
- SPACEBRIDGE_TEST_API_KEY: API key for SpaceBridge
- JIRA_URL: Jira instance URL (e.g., https://example.atlassian.net)
- JIRA_API_KEY: Jira API token
- JIRA_USERNAME: Jira username/email
- JIRA_TEST_PROJECT: Test project key (e.g., "TEST")

Usage:
    pytest tests/integration/mcp/test_jira_mcp.py -v -s
"""

import base64
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
JIRA_URL = os.getenv("JIRA_URL", "").rstrip("/")
JIRA_API_KEY = os.getenv("JIRA_API_KEY", "")
JIRA_USERNAME = os.getenv("JIRA_USERNAME", "")
JIRA_TEST_PROJECT = os.getenv("JIRA_TEST_PROJECT", "")  # e.g., "TEST"

# Test identifier
TEST_RUN_ID = f"mcp_test_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def jira_client():
    """Create Jira API client."""
    if not JIRA_API_KEY or not JIRA_USERNAME:
        pytest.skip("JIRA_API_KEY and JIRA_USERNAME required")

    auth_str = f"{JIRA_USERNAME}:{JIRA_API_KEY}"
    encoded_auth = base64.b64encode(auth_str.encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded_auth}",
        "Content-Type": "application/json",
    }
    with httpx.Client(base_url=JIRA_URL, headers=headers) as client:
        yield client


@pytest.mark.integration
@pytest.mark.mcp
@pytest.mark.skipif(
    not all(
        [
            SPACEBRIDGE_URL,
            SPACEBRIDGE_API_KEY,
            JIRA_URL,
            JIRA_API_KEY,
            JIRA_USERNAME,
            JIRA_TEST_PROJECT,
        ]
    ),
    reason="All Jira environment variables required",
)
def test_jira_mcp_integration(jira_client):
    """
    Complete MCP integration test for Jira tracker.

    This test:
    - Sets up Claude MCP server connection
    - Creates an issue via MCP
    - Searches for the issue
    - Gets issue details
    - Updates the issue
    - Verifies updates in Jira
    - Cleans up
    """
    print("\n" + "=" * 80)
    print("JIRA MCP INTEGRATION TEST")
    print("=" * 80)

    created_issue_id = None
    created_issue_key = None

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
            JIRA_TEST_PROJECT,
            issue_title,
            issue_description,
            timeout=60,
        )
        print(f"✓ Created issue via MCP: {created_issue_id}")

        # Extract issue key (Jira returns keys like "TEST-123")
        created_issue_key = created_issue_id

        # Step 3: Wait for indexing and search for issue
        print("\n" + "=" * 80)
        print("STEP 3: Search for Issue via MCP")
        print("=" * 80)

        time.sleep(10)  # Give time for indexing
        search_results = mcp_search_issue(
            "spacebridge", issue_title, project=JIRA_TEST_PROJECT, limit=10
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

        # Step 6: Verify update in Jira
        print("\n" + "=" * 80)
        print("STEP 6: Verify Update in Jira")
        print("=" * 80)

        time.sleep(5)  # Give time for sync
        jira_issue_response = jira_client.get(f"/rest/api/3/issue/{created_issue_key}")
        jira_issue_response.raise_for_status()
        jira_issue = jira_issue_response.json()

        assert jira_issue["fields"]["summary"] == updated_title, (
            f"Title not synced to Jira: got '{jira_issue['fields']['summary']}', "
            f"expected '{updated_title}'"
        )

        # Verify description (extract text from Jira's ADF format)
        jira_description = ""
        if jira_issue["fields"].get("description"):
            desc_content = jira_issue["fields"]["description"].get("content", [])
            for block in desc_content:
                for content in block.get("content", []):
                    if content.get("type") == "text":
                        jira_description += content.get("text", "")

        assert "Updated via MCP" in jira_description, "Description not synced to Jira"

        print("✓ Update propagated to Jira")
        print("\n✅ Jira MCP integration test PASSED")

    finally:
        # Cleanup
        print("\n" + "=" * 80)
        print("CLEANUP")
        print("=" * 80)

        # Delete created issue from Jira
        if created_issue_key:
            try:
                jira_client.delete(f"/rest/api/3/issue/{created_issue_key}")
                print(f"✓ Deleted Jira issue {created_issue_key}")
            except Exception as e:
                print(f"✗ Failed to delete Jira issue: {e}")

        cleanup_claude_mcp_server()
