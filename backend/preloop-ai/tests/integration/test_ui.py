import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("PRELOOP_TEST_URL")
USERNAME = os.environ.get("PRELOOP_TEST_USERNAME")
PASSWORD = os.environ.get("PRELOOP_TEST_PASSWORD")


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
    # 1. Visit the target URL
    # The test starts by navigating the browser to the specified web application.
    page.goto(f"{BASE_URL}/")

    # 2. Locate the main app shell component.
    # Playwright's locators can pierce shadow DOM boundaries automatically,
    # so we can directly look for elements within the <lit-app> component.
    lit_app_shell = page.locator("lit-app")

    # 3. Find and click the "Sign In" button within the shadow DOM.
    # We wait for the button to be visible before interacting with it to ensure the app is ready.
    sign_in_button = lit_app_shell.locator('sl-button:has-text("Sign In")')
    expect(sign_in_button).to_be_visible(
        timeout=10000
    )  # Increased timeout for initial load
    sign_in_button.click()

    # 4. Wait until the login page/view loads.
    # After clicking "Sign In", we expect the <login-view> component to appear.
    login_view = lit_app_shell.locator("login-view")
    expect(login_view).to_be_visible()
    # login_view.screenshot(path="login.png")

    # 5. Fill in the login credentials and submit the form.
    # We locate the Shoelace (sl-*) input components by their name attribute
    # and the submit button by its type.
    # NOTE: Replace with your actual test credentials.
    username_input = login_view.locator('sl-input[name="username"]').locator("input")
    password_input = login_view.locator('sl-input[name="password"]').locator("input")
    submit_button = login_view.locator('sl-button[type="submit"]')

    username_input.fill(USERNAME)
    password_input.fill(PASSWORD)
    submit_button.click()

    # 6. Wait for successful login and check that the dashboard has loaded.
    # We assert that the <dashboard-view> component is visible within a few seconds,
    # which confirms that the login was successful and navigation occurred.
    dashboard_view = lit_app_shell.locator("dashboard-view")
    expect(dashboard_view).to_be_visible(timeout=5000)

    # Optional: A final check for a specific element on the dashboard for robustness.
    # For example, checking for a heading.
    dashboard_heading = dashboard_view.locator("h1")
    expect(dashboard_heading).to_contain_text("Overview")
