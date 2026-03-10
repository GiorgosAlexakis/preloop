# Preloop Testing Strategy

This document outlines the testing strategy for the Preloop application, covering unit, integration, and production smoke tests.

## Unit Tests

Unit tests are designed to test individual components in isolation. They are written using `pytest` for the backend and Web Test Runner for the frontend.

### Coverage

Code coverage is measured for all components and is enforced in the CI/CD pipeline. The goal is to maintain a high level of coverage, with a target of at least 75% overall (CI `--fail-under=60`) and 80% for most components.

### Running Tests

```bash
# Backend (requires DATABASE_URL and PostgreSQL)
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/preloop"
pytest -m "not integration" -v

# With coverage
pytest -m "not integration" --cov=preloop --cov-report=term-missing --cov-report=html

# Quick unit tests (no database; use mocks)
pytest backend/tests/utils backend/tests/schemas backend/tests/models/test_db_session.py backend/tests/test_tokens_util.py -v

# Frontend
cd frontend && npm run test
```

### Current Status & Progress

Significant progress has been made in increasing unit test coverage for the backend.

**Models & CRUD:** `issue.py`, `issue_duplicate.py`, `organization.py`, `project.py`, `account.py`, `policy_snapshot.py`, `registration_token.py`, `instance.py`, `tool_access_rule.py` meet or exceed 80%.

**Sync:** `core.py` (scanner), `event_bus.py`, `base.py`, `manager.py` exceed 80%. `sync/utils.py` (retry, safe_exit) at 100%.

**API Endpoints:** `issues.py` (70%), `issue_duplicates.py` (70%), `issue_compliance.py` (100%), `embedding.py`, `roles.py`, `version.py`, `account.py`, `public_approval.py`, `policies.py` have comprehensive tests.

**Services:** `approval_service.py` (63%), `policy_evaluator.py`, `approval_wrapper.py`, `execution_metrics.py`, `push_proxy.py` have substantial coverage.

**Schemas:** `invitation`, `team`, `user`, `installers` at 100%.

**Utils:** `tokens`, `hashing`, `audit`, `permissions`, `redaction`, `encryption`, `request` at 100%.

### CI/CD Integration

All backend unit tests are organized into separate jobs in the `.gitlab-ci.yml` pipeline. This allows for parallel execution and clear reporting on the test status of each component, such as `test:unit:spacemodels`, `test:unit:preloop-sync`, and individual endpoint tests like `test:unit:preloop-endpoints-mcp`.

### Mutation Testing

To ensure the quality of our tests, we use mutation testing to identify and improve weak tests that are not effectively testing the code.

### Detailed Coverage Plan

See [docs/TEST_COVERAGE_PLAN.md](docs/TEST_COVERAGE_PLAN.md) for the full coverage plan, measuring instructions, and phase-by-phase implementation history.

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
