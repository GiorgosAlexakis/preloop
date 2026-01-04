# Preloop Testing Strategy

This document outlines the testing strategy for the Preloop application, covering unit, integration, and production smoke tests.

## Unit Tests

Unit tests are designed to test individual components in isolation. They are written using `pytest` for the backend and Web Test Runner for the frontend.

### Coverage

Code coverage is measured for all components and is enforced in the CI/CD pipeline. The goal is to maintain a high level of coverage, with a target of at least 80% for most components and 90% for critical components.

### Current Status & Progress

Significant progress has been made in increasing unit test coverage for the backend.
- **`backend/preloop/models/crud`**: Coverage has been substantially improved for key modules, with `issue.py`, `issue_duplicate.py`, `organization.py`, `project.py`, and `account.py` now meeting or exceeding the 80% coverage target.
- **`backend/preloop/sync/scanner`**: Coverage has been substantially improved for the core scanning logic, with `core.py` now exceeding the 80% coverage target.
- **`backend/preloop/sync/services`**: Coverage has been substantially improved for key modules, with `event_bus.py`, `base.py`, and `manager.py` now meeting or exceeding the 80% coverage target.
- **`backend/preloop/sync/trackers`**: Work has begun on improving coverage for the core tracker logic, with initial tests added for `base.py`, `github.py`, `gitlab.py`, and `jira.py`.
- **`backend/preloop/api/endpoints`**: Comprehensive unit tests have been added for the new `/api/v1/mcp/` endpoints in `tests/endpoints/test_mcp.py`, covering all new MCP tools.

### CI/CD Integration

All backend unit tests are organized into separate jobs in the `.gitlab-ci.yml` pipeline. This allows for parallel execution and clear reporting on the test status of each component, such as `test:unit:spacemodels`, `test:unit:preloop-sync`, and individual endpoint tests like `test:unit:preloop-endpoints-mcp`.

### Mutation Testing

To ensure the quality of our tests, we use mutation testing to identify and improve weak tests that are not effectively testing the code.

## Integration and Functional Tests

Integration and functional tests are designed to test the application as a whole, including its interactions with external services.

### Test Environment

A dedicated test environment is set up in a Kubernetes cluster. The CI/CD pipeline automatically deploys feature branches to this environment, allowing for automated testing of new features.

### API Tests

API integration tests are written using `pytest` and `httpx`. They cover end-to-end user flows, such as creating a project, adding a tracker, and searching for issues.

#### MCP Integration Tests

Integration tests for MCP endpoints are part of the tracker synchronization test suite:
- `tests/integration/test_tracker_sync_github.py`
- `tests/integration/test_tracker_sync_gitlab.py`
- `tests/integration/test_tracker_sync_jira.py`

These tests use a direct Python MCP client (`tests/integration/mcp_client.py`) that connects via HTTP to the Preloop MCP endpoint. This approach provides:
- **Fast execution**: Direct HTTP calls instead of spawning CLI processes
- **Reliable testing**: Uses the official `mcp` Python client library
- **Complete coverage**: Tests MCP tools (`create_issue`, `get_issue`, `update_issue`, `search`) alongside tracker sync functionality

The tests verify the entire request/response cycle, including authentication, data validation, and service logic. They run automatically in the CI/CD pipeline against dynamically created test environments.

### UI Tests

UI functional tests are written using Playwright. They simulate user actions, such as logging in, navigating the application, and interacting with UI elements. The tests are configured to record screenshots and generate videos on failure.

## Production Smoke Tests

Production smoke tests are designed to perform a quick, high-level check to ensure that the production and staging environments are up and running. They simulate a standard user workflow to verify that the core functionality is working as expected.

### Schedule

Smoke tests are run on a schedule (e.g., every hour) and are configured to send notifications if the tests fail.
