"""
Common utilities for tracker synchronization tests.

This module contains shared configuration and helper functions for
GitHub, GitLab, and Jira integration tests.

Note: Fixtures are defined in conftest.py
"""

import os
import time
import uuid
from typing import Any, Dict
from urllib.parse import quote

import httpx

# Test configuration
PRELOOP_URL = os.getenv("PRELOOP_TEST_URL", "").rstrip("/")
PRELOOP_API_KEY = os.getenv("PRELOOP_TEST_API_KEY", "")

# Timeouts
INDEX_TIMEOUT = int(os.getenv("INDEX_TIMEOUT", "300"))  # 5 minutes
WEBHOOK_PROPAGATION_TIMEOUT = int(
    os.getenv("WEBHOOK_PROPAGATION_TIMEOUT", "60")
)  # 1 minute

# Test identifier - unique suffix for this test run
TEST_RUN_ID = f"test_{uuid.uuid4().hex[:8]}"


# Helper functions
def wait_for_issue(
    client: httpx.Client, issue_key: str, timeout: int
) -> Dict[str, Any]:
    """Poll Preloop AI until issue is available or timeout."""
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
    """Poll Preloop AI until issue title matches expected value or timeout."""
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
