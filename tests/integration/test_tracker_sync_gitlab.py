"""
Integration test for GitLab tracker synchronization with SpaceBridge.

This test verifies the complete end-to-end flow including:
- Tracker registration
- Initial issue indexing via polling
- Webhook registration and propagation
- Bi-directional sync (GitLab -> SpaceBridge, SpaceBridge -> GitLab)
- Comment synchronization
- MCP tools integration
- Proper cleanup

Environment Variables Required:
- SPACEBRIDGE_TEST_URL: SpaceBridge instance URL
- SPACEBRIDGE_TEST_API_KEY: API key for SpaceBridge authentication
- GITLAB_URL: GitLab instance URL (e.g., https://gitlab.com)
- GITLAB_API_KEY: GitLab personal access token
- GITLAB_ISSUE_KEY: Test issue in format "group/project#123"
- GITLAB_ORG_ID: Group ID (for scope filtering)
- GITLAB_PROJECT_ID: Project ID (for scope filtering)

Usage:
    pytest tests/integration/test_tracker_sync_gitlab.py -v -s
"""

import json
import os
import re
import time
from urllib.parse import quote, quote as url_quote

import httpx
import pytest

from tests.integration.test_tracker_sync_common import (
    INDEX_TIMEOUT,
    SPACEBRIDGE_API_KEY,
    SPACEBRIDGE_URL,
    TEST_RUN_ID,
    WEBHOOK_PROPAGATION_TIMEOUT,
    wait_for_issue,
    wait_for_issue_update,
)

# GitLab config
GITLAB_URL = os.getenv("GITLAB_URL", "https://gitlab.com").rstrip("/")
GITLAB_API_KEY = os.getenv("GITLAB_API_KEY", "")
GITLAB_ISSUE_KEY = os.getenv("GITLAB_ISSUE_KEY", "")  # e.g., "group/project#123"
GITLAB_ORG_ID = os.getenv("GITLAB_ORG_ID", "")  # Group ID
GITLAB_PROJECT_ID = os.getenv("GITLAB_PROJECT_ID", "")  # Project ID


@pytest.fixture(scope="module")
def gitlab_client():
    """Create GitLab API client."""
    if not GITLAB_API_KEY:
        pytest.skip("GITLAB_API_KEY required")

    headers = {"PRIVATE-TOKEN": GITLAB_API_KEY}
    with httpx.Client(base_url=f"{GITLAB_URL}/api/v4", headers=headers) as client:
        yield client


def parse_gitlab_issue_key(issue_key: str):
    """Parse GitLab issue key into project path and iid."""
    # Format: group/project#123
    project_path, iid = issue_key.split("#")
    return project_path, iid


@pytest.mark.integration
@pytest.mark.gitlab
@pytest.mark.skipif(
    not all([GITLAB_API_KEY, GITLAB_ISSUE_KEY]),
    reason="GITLAB_API_KEY and GITLAB_ISSUE_KEY required",
)
def test_gitlab_tracker_sync(spacebridge_client, gitlab_client):
    """
    Complete integration test for GitLab tracker synchronization.

    This test verifies:
    - Tracker registration
    - Initial issue indexing via polling
    - Webhook registration and propagation
    - Bi-directional sync (GitLab -> SpaceBridge, SpaceBridge -> GitLab)
    - Comment synchronization
    - MCP tools integration
    - Proper cleanup
    """
    print("\n" + "=" * 80)
    print("GITLAB TRACKER SYNC TEST")
    print("=" * 80)

    # Parse GitLab issue key
    project_path, iid = parse_gitlab_issue_key(GITLAB_ISSUE_KEY)

    # Build scope rules to only sync specific org and project
    scope_rules = []
    if GITLAB_ORG_ID and GITLAB_PROJECT_ID:
        scope_rules = [
            {
                "scope_type": "ORGANIZATION",
                "rule_type": "INCLUDE",
                "identifier": GITLAB_ORG_ID,
            },
            {
                "scope_type": "PROJECT",
                "rule_type": "INCLUDE",
                "identifier": GITLAB_PROJECT_ID,
            },
        ]

    # Variables for cleanup
    tracker_id = None
    original_title = None
    original_description = None
    created_comment_ids = []

    try:
        # Step 2: Register tracker
        print("\n" + "=" * 80)
        print("STEP 2: Tracker Registration (GitLab)")
        print("=" * 80)

        request_body = {
            "name": f"GitLab Test Tracker {TEST_RUN_ID}",
            "type": "gitlab",
            "api_key": GITLAB_API_KEY,
            "config": {
                "url": GITLAB_URL,
            },
            "scope_rules": scope_rules,
        }

        print("Request body (api_key redacted):")
        redacted_body = request_body.copy()
        redacted_body["api_key"] = "***REDACTED***"
        print(json.dumps(redacted_body, indent=2))

        register_response = spacebridge_client.post(
            "/api/v1/trackers",
            json=request_body,
        )
        assert register_response.status_code == 201, (
            f"Failed to register GitLab tracker (status {register_response.status_code}): {register_response.text}"
        )
        tracker_data = register_response.json()
        tracker_id = tracker_data["id"]
        print(f"✓ Registered GitLab tracker: {tracker_id}")
        print("Response data:")
        print(json.dumps(tracker_data, indent=2))

        # Step 3: Verify tracker is listed
        print("\n" + "=" * 80)
        print("STEP 3: Tracker Verification")
        print("=" * 80)

        list_response = spacebridge_client.get("/api/v1/trackers")
        assert list_response.status_code == 200
        trackers = list_response.json()
        assert any(t["id"] == tracker_id for t in trackers), (
            "GitLab tracker not in list"
        )
        print("✓ GitLab tracker appears in tracker list")

        # Step 5: Wait for initial indexing
        print("\n" + "=" * 80)
        print("STEP 5: Initial Indexing (Polling)")
        print("=" * 80)

        issue_data = wait_for_issue(spacebridge_client, GITLAB_ISSUE_KEY, INDEX_TIMEOUT)
        original_title = issue_data["title"]
        original_description = issue_data.get("description", "")
        print(f"✓ Issue indexed: {GITLAB_ISSUE_KEY}")
        print(f"  Original title: {original_title}")

        # Step 7: Update issue via GitLab API
        print("\n" + "=" * 80)
        print("STEP 7: External Update (GitLab API)")
        print("=" * 80)

        new_title = f"{original_title} {TEST_RUN_ID}"
        new_description = f"{original_description} {TEST_RUN_ID}"

        # URL encode project path for GitLab API
        encoded_project_path = url_quote(project_path, safe="")

        update_response = gitlab_client.put(
            f"/projects/{encoded_project_path}/issues/{iid}",
            json={"title": new_title, "description": new_description},
        )
        update_response.raise_for_status()
        print("✓ Updated issue via GitLab API")
        print(f"  New title: {new_title}")

        # Step 8: Wait for webhook propagation
        print("\n" + "=" * 80)
        print("STEP 8: Webhook Propagation Test")
        print("=" * 80)

        updated_issue = wait_for_issue_update(
            spacebridge_client, GITLAB_ISSUE_KEY, new_title, WEBHOOK_PROPAGATION_TIMEOUT
        )
        assert updated_issue["title"] == new_title
        assert TEST_RUN_ID in updated_issue.get("description", "")
        print("✓ Webhook propagation successful")

        # Step 9: Create comment via GitLab API
        print("\n" + "=" * 80)
        print("STEP 9: Comment Sync Test")
        print("=" * 80)

        comment_text = f"Test comment {TEST_RUN_ID}"
        comment_response = gitlab_client.post(
            f"/projects/{encoded_project_path}/issues/{iid}/notes",
            json={"body": comment_text},
        )
        comment_response.raise_for_status()
        comment_id = str(comment_response.json()["id"])
        created_comment_ids.append(comment_id)
        print(f"✓ Created comment via GitLab API: {comment_id}")

        # Wait for comment to appear in SpaceBridge
        print("  Waiting for comment to sync...")
        time.sleep(10)  # Give webhook time to propagate
        issue_with_comments = wait_for_issue(
            spacebridge_client, GITLAB_ISSUE_KEY, WEBHOOK_PROPAGATION_TIMEOUT
        )
        print(f"  Issue response: {issue_with_comments}")
        print(f"  Comments in response: {issue_with_comments.get('comments', [])}")
        print(f"  Looking for comment text: '{comment_text}'")
        assert any(
            comment_text in c.get("body", "")
            for c in issue_with_comments.get("comments", [])
        ), (
            f"Comment not synced to SpaceBridge. Got {len(issue_with_comments.get('comments', []))} comments: {issue_with_comments.get('comments', [])}"
        )
        print("✓ Comment synced to SpaceBridge")

        # Step 10: Update issue via SpaceBridge API (remove test suffix)
        print("\n" + "=" * 80)
        print("STEP 10: SpaceBridge Update")
        print("=" * 80)

        # URL-encode the issue key for the PUT request
        encoded_issue_key = quote(GITLAB_ISSUE_KEY, safe="")
        update_response = spacebridge_client.put(
            f"/api/v1/issues/{encoded_issue_key}",
            json={
                "title": original_title,
                "description": original_description,
            },
        )
        assert update_response.status_code == 200, (
            f"Failed to update issue via SpaceBridge: {update_response.text}"
        )
        print("✓ Updated issue via SpaceBridge API")

        # Step 11: Verify update propagated to GitLab
        print("\n" + "=" * 80)
        print("STEP 11: Tracker Verification (GitLab)")
        print("=" * 80)

        time.sleep(5)  # Give sync time to complete
        verify_response = gitlab_client.get(
            f"/projects/{encoded_project_path}/issues/{iid}"
        )
        verify_response.raise_for_status()
        gitlab_issue = verify_response.json()
        assert gitlab_issue["title"] == original_title, (
            f"Title not synced to GitLab: got '{gitlab_issue['title']}', expected '{original_title}'"
        )
        assert gitlab_issue["description"] == original_description, (
            "Description not synced to GitLab"
        )

        print("✓ Update propagated from SpaceBridge to GitLab")

        # Step 12: Test MCP Tools
        print("\n" + "=" * 80)
        print("STEP 12: MCP Tools Integration Test")
        print("=" * 80)

        # Setup MCP server
        from tests.integration.helpers import (
            cleanup_claude_mcp_server,
            mcp_create_issue,
            mcp_get_issue,
            mcp_search_issue,
            mcp_update_issue,
            setup_claude_mcp_server,
            verify_mcp_server,
        )

        setup_claude_mcp_server(SPACEBRIDGE_URL, SPACEBRIDGE_API_KEY)
        verify_mcp_server()
        print("✓ MCP server setup complete")

        # Test create_issue via MCP
        create_title = f"MCP Test Issue {TEST_RUN_ID}"
        create_description = f"Issue created via MCP for testing - {TEST_RUN_ID}"
        create_output = mcp_create_issue(
            "spacebridge",
            project_path,
            title=create_title,
            description=create_description,
        )
        assert len(create_output) > 0, "MCP create_issue returned empty output"
        print(f"  MCP create_issue output: {create_output[:500]}")
        # Extract issue key from create output (look for pattern like group/project#123)
        issue_key_match = re.search(
            r"([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+#\d+)", create_output
        )
        created_issue_key = None
        if issue_key_match:
            created_issue_key = issue_key_match.group(1)
            print(f"✓ Created issue via MCP: {created_issue_key}")
        else:
            print("✓ Created issue via MCP create_issue (key not found in output)")

        # Wait for issue to be created and indexed
        time.sleep(5)

        # Test search via MCP to find the created issue
        search_output = mcp_search_issue(
            "spacebridge", create_title, project=project_path, limit=10
        )
        assert len(search_output) > 0, "MCP search returned empty output"
        assert TEST_RUN_ID in search_output, (
            f"Created issue with {TEST_RUN_ID} not found in MCP search results"
        )
        print("✓ Found created issue via MCP search")

        # If we didn't get the key from create, try to extract from search
        if not created_issue_key:
            print(f"  MCP search output: {search_output[:500]}")
            issue_key_match = re.search(
                r"([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+#\d+)", search_output
            )
            if issue_key_match:
                created_issue_key = issue_key_match.group(1)

        if not created_issue_key:
            raise AssertionError(
                f"Could not extract issue key from MCP output. "
                f"Please check MCP create and search output format.\n"
                f"Create output: {create_output[:200]}\n"
                f"Search output: {search_output[:200]}"
            )

        # Test update_issue via MCP to close the issue
        close_output = mcp_update_issue(
            "spacebridge",
            created_issue_key,
            status="closed",
        )
        assert len(close_output) > 0, "MCP update_issue (close) returned empty output"
        print("✓ Closed issue via MCP update_issue")

        # Test get_issue via MCP to verify it's closed
        time.sleep(3)
        get_output = mcp_get_issue("spacebridge", created_issue_key)
        assert len(get_output) > 0, "MCP get_issue returned empty output"
        assert "closed" in get_output.lower() or "done" in get_output.lower(), (
            "Issue does not appear to be closed in MCP get_issue output"
        )
        print("✓ Verified issue is closed via MCP get_issue")

        cleanup_claude_mcp_server()
        print("✓ MCP server cleanup complete")
        print("\n✅ GitLab tracker sync test PASSED (including MCP)")

    finally:
        # Cleanup
        print("\n" + "=" * 80)
        print("CLEANUP")
        print("=" * 80)

        # Delete created comments
        encoded_project_path = url_quote(project_path, safe="")
        for comment_id in created_comment_ids:
            try:
                gitlab_client.delete(
                    f"/projects/{encoded_project_path}/issues/{iid}/notes/{comment_id}"
                )
                print(f"✓ Deleted comment: {comment_id}")
            except Exception as e:
                print(f"✗ Failed to delete comment {comment_id}: {e}")

        # Note: We intentionally don't restore the issue title/description
        # since the SpaceBridge update in Step 10 already restored them
