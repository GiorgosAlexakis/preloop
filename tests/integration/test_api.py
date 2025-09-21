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
    response = client.get("/api/v1/trackers")
    assert response.status_code == 200
    trackers_response = response.json()
    assert len(trackers_response) == 0
