"""
Pytest configuration and fixtures for integration tests.
"""

import os

import httpx
import pytest

# Test configuration
SPACEBRIDGE_URL = os.getenv("SPACEBRIDGE_TEST_URL", "").rstrip("/")
SPACEBRIDGE_API_KEY = os.getenv("SPACEBRIDGE_TEST_API_KEY", "")


@pytest.fixture(scope="module")
def spacebridge_client():
    """Create SpaceBridge HTTP client with authentication."""
    if not SPACEBRIDGE_URL or not SPACEBRIDGE_API_KEY:
        pytest.skip("SPACEBRIDGE_TEST_URL and SPACEBRIDGE_TEST_API_KEY required")

    headers = {
        "Authorization": f"Bearer {SPACEBRIDGE_API_KEY}",
        "Content-Type": "application/json",
    }
    with httpx.Client(
        base_url=SPACEBRIDGE_URL, headers=headers, timeout=30.0
    ) as client:
        yield client


@pytest.mark.integration
def test_spacebridge_health(spacebridge_client):
    """
    Health Check: Verify SpaceBridge instance is running and accessible.
    """
    print("\n" + "=" * 80)
    print("STEP 1: Health Check")
    print("=" * 80)

    response = spacebridge_client.get("/api/v1/health")
    assert response.status_code == 200, f"Health check failed: {response.text}"
    print("✓ SpaceBridge instance is healthy")
