import os
import pytest
from playwright.sync_api import Page, expect

STAGING_URL = "https://staging.spacebridge.io"
PRODUCTION_URL = "https://spacebridge.io"
USERNAME = os.environ.get("SPACEBRIDGE_USERNAME")
PASSWORD = os.environ.get("SPACEBRIDGE_PASSWORD")


@pytest.mark.parametrize("base_url", [STAGING_URL, PRODUCTION_URL])
@pytest.mark.skipif(not all([USERNAME, PASSWORD]), reason="Missing test credentials")
def test_smoke(page: Page, base_url):
    page.goto(base_url)

    # 1. Log in to the application
    page.fill("input[name='email']", USERNAME)
    page.fill("input[name='password']", PASSWORD)
    page.click("button[type='submit']")
    expect(page.locator("h1")).to_have_text("Dashboard")

    # 2. Navigate to a project with a configured tracker
    # (This will require a pre-configured project and tracker in the test account)
    page.click("text=Projects")
    page.click("text=Test Project")

    # 3. Update an issue in the tracker
    # (This will require a pre-existing issue in the test tracker)
    page.click("text=Issues")
    page.click("text=Test Issue")
    page.fill("textarea[name='comment']", "This is a test comment from the smoke test.")
    page.click("text=Add Comment")

    # 4. Verify that SpaceBridge receives the webhook and updates the issue
    # (This will require a way to query the SpaceBridge database or API)
    # For now, we'll just check that the comment appears in the UI
    expect(
        page.locator("text=This is a test comment from the smoke test.")
    ).to_be_visible()
