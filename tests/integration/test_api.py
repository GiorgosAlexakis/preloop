import os
import httpx
import pytest

BASE_URL = os.environ.get("SPACEBRIDGE_TEST_URL")
API_KEY = os.environ.get("SPACEBRIDGE_TEST_API_KEY")


@pytest.fixture(scope="module")
def client():
    if not BASE_URL or not API_KEY:
        pytest.fail("SPACEBRIDGE_TEST_URL or SPACEBRIDGE_TEST_API_KEY not set")

    headers = {"Authorization": f"Bearer {API_KEY}"}
    with httpx.Client(base_url=BASE_URL, headers=headers) as client:
        yield client


def test_project_lifecycle(client):
    # 1. Get organization
    response = client.get("/api/v1/organizations")
    assert response.status_code == 200
    orgs_response = response.json()
    assert orgs_response["total"] > 0, "No organizations found for the test user."
    organization_id = orgs_response["items"][0]["id"]

    # 2. Create a new project
    project_data = {
        "name": "Integration Test Project",
        "description": "A temporary project for integration testing.",
        "identifier": "integration-test-project",
        "organization_id": organization_id,
    }
    response = client.post("/api/v1/projects", json=project_data)
    assert response.status_code == 201, f"Failed to create project: {response.text}"
    project = response.json()
    project_id = project["id"]

    # 3. Get the project to verify creation
    response = client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Integration Test Project"

    # 4. Delete the project
    response = client.delete(f"/api/v1/projects/{project_id}")
    assert response.status_code == 204

    # 5. Verify deletion
    response = client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 404
