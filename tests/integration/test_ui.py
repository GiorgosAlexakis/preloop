import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("SPACEBRIDGE_TEST_URL")
USERNAME = os.environ.get("SPACEBRIDGE_TEST_USERNAME")
PASSWORD = os.environ.get("SPACEBRIDGE_TEST_PASSWORD")


@pytest.mark.skipif(
    not all([BASE_URL, USERNAME, PASSWORD]), reason="Missing test credentials"
)
def test_login_and_dashboard(page: Page):
    page.goto(BASE_URL)

    # Log in to the application
    page.fill("input[name='email']", USERNAME)
    page.fill("input[name='password']", PASSWORD)
    page.click("button[type='submit']")

    # Verify that the dashboard is displayed
    expect(page.locator("h1")).to_have_text("Dashboard")
