"""
Playwright E2E tests for Preloop frontend critical user flows.

Requires PRELOOP_TEST_URL, PRELOOP_TEST_USERNAME, PRELOOP_TEST_PASSWORD to be set.
Run with: pytest backend/tests/integration/test_ui*.py -v
"""

import os
import re
import time
from pathlib import Path
from typing import Generator

import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("PRELOOP_TEST_URL", "").rstrip("/")
USERNAME = os.environ.get("PRELOOP_TEST_USERNAME")
PASSWORD = os.environ.get("PRELOOP_TEST_PASSWORD")

SKIP_E2E = not all([BASE_URL, USERNAME, PASSWORD])

SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def capture_screenshot_on_failure(
    request: pytest.FixtureRequest, page: Page
) -> Generator[None, None, None]:
    """Capture a screenshot if the test fails."""
    yield
    if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
        SCREENSHOTS_DIR.mkdir(exist_ok=True)
        screenshot_path = SCREENSHOTS_DIR / f"{request.node.name}.png"
        page.screenshot(path=str(screenshot_path))
        print(f"Screenshot saved to: {screenshot_path}")


def _login(page: Page) -> None:
    """Helper to perform login. Assumes page can navigate to login."""
    assert USERNAME is not None and PASSWORD is not None
    page.goto(f"{BASE_URL}/login", timeout=15000)
    lit_app_shell = page.locator("lit-app")
    expect(lit_app_shell).to_be_visible(timeout=10000)
    login_view = lit_app_shell.locator("login-view")
    expect(login_view).to_be_visible(timeout=10000)
    username_input = login_view.locator('sl-input[name="username"]').locator("input")
    password_input = login_view.locator('sl-input[name="password"]').locator("input")
    submit_button = login_view.locator('sl-button[type="submit"]')
    expect(username_input).to_be_visible(timeout=5000)
    expect(password_input).to_be_visible(timeout=5000)
    username_input.fill(USERNAME)
    password_input.fill(PASSWORD)
    submit_button.click()
    dashboard_view = lit_app_shell.locator("dashboard-view")
    expect(dashboard_view).to_be_visible(timeout=10000)


@pytest.mark.skipif(SKIP_E2E, reason="Missing test credentials")
def test_registration_flow(page: Page) -> None:
    """
    Navigate to /register, fill form, submit, assert redirect to login or dashboard.
    Uses unique username/email to avoid conflicts with existing users.
    """
    unique_suffix = str(int(time.time() * 1000))
    username = f"e2e_test_{unique_suffix}"
    email = f"e2e_test_{unique_suffix}@example.com"
    password = "TestPassword123!"

    page.goto(f"{BASE_URL}/register", timeout=15000)

    lit_app_shell = page.locator("lit-app")
    expect(lit_app_shell).to_be_visible(timeout=10000)

    # If registration is disabled, we get redirected to login
    if "/login" in page.url:
        assert "/login" in page.url
        return

    register_view = lit_app_shell.locator("register-view")
    expect(register_view).to_be_visible(timeout=10000)

    username_input = register_view.locator('sl-input[name="username"]').locator("input")
    email_input = register_view.locator('sl-input[name="email"]').locator("input")
    password_input = register_view.locator('sl-input[name="password"]').locator("input")
    submit_button = register_view.locator('sl-button[type="submit"]')

    expect(username_input).to_be_visible(timeout=5000)
    expect(email_input).to_be_visible(timeout=5000)
    expect(password_input).to_be_visible(timeout=5000)

    username_input.fill(username)
    email_input.fill(email)
    password_input.fill(password)
    submit_button.click()

    # After submit: redirect to login (with ?registered=true) or dashboard
    # Billing-enabled instances may redirect to Stripe - allow any redirect
    page.wait_for_url(
        lambda u: (
            "/login" in str(u) or "/console" in str(u) or "stripe" in str(u).lower()
        ),
        timeout=15000,
    )
    assert (
        "/login" in page.url or "/console" in page.url or "stripe" in page.url.lower()
    )


@pytest.mark.skipif(SKIP_E2E, reason="Missing test credentials")
def test_add_tracker_flow(page: Page) -> None:
    """
    After login, navigate to /trackers, click add tracker, assert modal opens
    and form is visible. Does not submit (requires valid API token).
    """
    _login(page)

    page.goto(f"{BASE_URL}/console/trackers", timeout=15000)
    lit_app_shell = page.locator("lit-app")
    expect(lit_app_shell).to_be_visible(timeout=10000)

    trackers_view = lit_app_shell.locator("trackers-view")
    expect(trackers_view).to_be_visible(timeout=10000)

    add_button = trackers_view.locator('sl-button:has-text("Add New Tracker")')
    expect(add_button).to_be_visible(timeout=5000)
    add_button.click()

    add_tracker_modal = page.locator("add-tracker-modal")
    expect(add_tracker_modal).to_be_visible(timeout=5000)

    dialog = add_tracker_modal.locator('sl-dialog[label="Add Tracker"]')
    expect(dialog).to_be_visible(timeout=5000)

    name_input = add_tracker_modal.locator('sl-input[name="name"]')
    expect(name_input).to_be_visible(timeout=5000)

    name_input.locator("input").fill("E2E Test Tracker")
    type_select = add_tracker_modal.locator('sl-select[name="type"]')
    expect(type_select).to_be_visible(timeout=3000)


@pytest.mark.skipif(SKIP_E2E, reason="Missing test credentials")
def test_create_flow_flow(page: Page) -> None:
    """
    After login, navigate to /flows, click create flow, assert create flow page
    loads and minimal form is visible. Fills name and asserts form structure.
    """
    _login(page)

    page.goto(f"{BASE_URL}/console/flows", timeout=15000)
    lit_app_shell = page.locator("lit-app")
    expect(lit_app_shell).to_be_visible(timeout=10000)

    flows_view = lit_app_shell.locator("flows-view")
    expect(flows_view).to_be_visible(timeout=10000)

    create_button = flows_view.locator('sl-button:has-text("Create New Flow")')
    expect(create_button).to_be_visible(timeout=5000)
    create_button.click()

    page.wait_for_url(re.compile(r".*/console/flows/new.*"), timeout=10000)
    expect(page).to_have_url(re.compile(r".*/console/flows/new.*"))

    flow_view = lit_app_shell.locator("flow-view")
    expect(flow_view).to_be_visible(timeout=10000)

    view_header = flow_view.locator("view-header")
    expect(view_header).to_contain_text("Create Flow", timeout=5000)

    name_input = flow_view.locator("sl-input").first
    expect(name_input).to_be_visible(timeout=5000)
    name_input.locator("input").fill("E2E Test Flow")
