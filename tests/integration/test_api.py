import os
import httpx
import pytest

BASE_URL = os.environ.get("SPACEBRIDGE_TEST_URL")
API_KEY = os.environ.get("SPACEBRIDGE_API_KEY")


@pytest.fixture(scope="module")
def client():
    if not BASE_URL or not API_KEY:
        pytest.skip("SPACEBRIDGE_TEST_URL or SPACEBRIDGE_API_KEY not set")

    headers = {"Authorization": f"Bearer {API_KEY}"}
    with httpx.Client(base_url=BASE_URL, headers=headers) as client:
        yield client


def test_project_and_tracker_lifecycle(client):
    # 1. Create a new project
    project_data = {
        "name": "Test Project",
        "description": "A temporary project for integration testing",
    }
    response = client.post("/api/v1/projects", json=project_data)
    assert response.status_code == 201
    project = response.json()
    project_id = project["id"]

    # 2. Add a tracker to the project
    tracker_data = {
        "type": "github",
        "config": {
            "repo_url": "https://github.com/spacecode-ai/oss-bot",
        },
    }
    response = client.post(f"/api/v1/projects/{project_id}/trackers", json=tracker_data)
    assert response.status_code == 201

    # 3. Delete the project
    response = client.delete(f"/api/v1/projects/{project_id}")
    assert response.status_code == 204
