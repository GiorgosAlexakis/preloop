import os
import httpx
import pytest

# Note on testing approach:
# The new MCP server is HTTP-based, providing REST endpoints for each tool.
# Standard MCP clients like `claude mcp` are designed for stdio-based servers
# and cannot directly call these HTTP endpoints.
# Therefore, the correct way to simulate an MCP client for integration testing
# is to use an HTTP client like `httpx` to make POST requests to the tool
# endpoints, which is what this test suite does.

BASE_URL = os.environ.get("SPACEBRIDGE_TEST_URL")
API_KEY = os.environ.get("SPACEBRIDGE_TEST_API_KEY")


@pytest.fixture(scope="module")
def client():
    if not BASE_URL or not API_KEY:
        pytest.fail("SPACEBRIDGE_TEST_URL or SPACEBRIDGE_TEST_API_KEY not set")

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    with httpx.Client(base_url=BASE_URL, headers=headers) as client:
        yield client


def test_mcp_issue_lifecycle_integration(client):
    """
    Integration test for the MCP issue lifecycle (create, get, update).
    This test simulates a user interacting with issues via an MCP client.
    It assumes the test environment is seeded with a 'spacebridge' project.
    """
    # 1. Create a new issue using the 'create_issue' tool
    create_payload = {
        "project": "spacebridge",
        "title": "MCP Integration Test Issue",
        "description": "An issue created via integration test.",
        "labels": ["test", "mcp"],
    }
    create_response = client.post("/api/v1/mcp/create_issue", json=create_payload)
    assert create_response.status_code == 200
    create_data = create_response.json()
    assert create_data["status"] == "created"
    issue_id = create_data["issue_id"]
    assert issue_id is not None

    # 2. Retrieve the created issue using the 'get_issue' tool
    get_payload = {"issue": issue_id}
    get_response = client.post("/api/v1/mcp/get_issue", json=get_payload)
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["id"] == issue_id
    assert get_data["title"] == "MCP Integration Test Issue"
    assert "test" in get_data["labels"]

    # 3. Update the issue using the 'update_issue' tool
    update_payload = {
        "issue": issue_id,
        "title": "MCP Integration Test Issue [Updated]",
        "status": "In Progress",
    }
    update_response = client.post("/api/v1/mcp/update_issue", json=update_payload)
    assert update_response.status_code == 200
    update_data = update_response.json()
    assert update_data["status"] == "updated"

    # 4. Verify the update by getting the issue again
    verify_response = client.post("/api/v1/mcp/get_issue", json=get_payload)
    assert verify_response.status_code == 200
    verify_data = verify_response.json()
    assert verify_data["title"] == "MCP Integration Test Issue [Updated]"
    assert verify_data["status"] == "In Progress"
