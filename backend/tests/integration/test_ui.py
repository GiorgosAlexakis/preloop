import os
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("PRELOOP_TEST_URL")
USERNAME = os.environ.get("PRELOOP_TEST_USERNAME")
PASSWORD = os.environ.get("PRELOOP_TEST_PASSWORD")

# Directory for screenshots on failure
SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"


@pytest.fixture(autouse=True)
def capture_screenshot_on_failure(request, page: Page):
    """Capture a screenshot if the test fails."""
    yield
    # After test execution, check if it failed
    if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
        SCREENSHOTS_DIR.mkdir(exist_ok=True)
        screenshot_path = SCREENSHOTS_DIR / f"{request.node.name}.png"
        page.screenshot(path=str(screenshot_path))
        print(f"Screenshot saved to: {screenshot_path}")


@pytest.mark.skipif(
    not all([BASE_URL, USERNAME, PASSWORD]), reason="Missing test credentials"
)
def test_lit_app_successful_login(page: Page):
    """
    This test verifies the login functionality of the Lit web application.
    It navigates to the site, clicks the sign-in button, fills out the
    login form within the web components, and asserts that the dashboard
    is visible after a successful login.
    """
    # 1. Navigate directly to the login page to avoid any landing page routing issues
    page.goto(f"{BASE_URL}/login")

    # 2. Wait for the page to load and locate the main app shell
    lit_app_shell = page.locator("lit-app")
    expect(lit_app_shell).to_be_visible(timeout=10000)

    # 3. Wait for the login-view to be visible
    # Use a longer timeout to account for JS hydration
    login_view = lit_app_shell.locator("login-view")
    expect(login_view).to_be_visible(timeout=10000)

    # 4. Fill in the login credentials and submit the form.
    # We locate the Shoelace (sl-*) input components by their name attribute
    username_input = login_view.locator('sl-input[name="username"]').locator("input")
    password_input = login_view.locator('sl-input[name="password"]').locator("input")
    submit_button = login_view.locator('sl-button[type="submit"]')

    # Wait for inputs to be ready
    expect(username_input).to_be_visible(timeout=5000)
    expect(password_input).to_be_visible(timeout=5000)

    username_input.fill(USERNAME)
    password_input.fill(PASSWORD)
    submit_button.click()

    # 5. Wait for successful login and check that the dashboard has loaded.
    # We assert that the <dashboard-view> component is visible,
    # which confirms that the login was successful and navigation occurred.
    dashboard_view = lit_app_shell.locator("dashboard-view")
    expect(dashboard_view).to_be_visible(timeout=10000)

    # Optional: A final check for a specific element on the dashboard for robustness.
    dashboard_heading = dashboard_view.locator("h1")
    expect(dashboard_heading).to_contain_text("Overview")
