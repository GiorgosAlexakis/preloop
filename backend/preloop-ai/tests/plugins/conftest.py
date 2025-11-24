"""Fixtures for plugin tests."""

import os
import pytest
from typing import Generator
import fastapi
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Disable RBAC before importing anything else that might use the decorator
os.environ["DISABLE_RBAC"] = "true"
# Enable DEV_MODE to prevent SPA catch-all from interfering with test routes
os.environ["DEV_MODE"] = "true"

from preloop_ai.api.app import create_app
from preloop_models.db.session import get_db_session
from preloop_ai.api.auth.jwt import get_current_active_user
from preloop_models.models.user import User


@pytest.fixture(scope="function")
def audit_app(
    db_session: Session, test_user: User
) -> Generator[fastapi.FastAPI, None, None]:
    """Create a FastAPI app for testing audit endpoints with the audit router included."""

    def override_get_current_active_user():
        return test_user

    def override_get_db():
        yield db_session

    # Include the audit router manually since plugins are skipped in testing mode
    from preloop_ai.plugins.proprietary.audit import endpoints as audit_endpoints

    app = create_app()

    # Include the audit router after app creation
    app.include_router(audit_endpoints.router, prefix="/api/v1", tags=["Audit"])

    # Override dependencies
    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_current_active_user] = override_get_current_active_user

    yield app


@pytest.fixture(scope="function")
def audit_client(audit_app: fastapi.FastAPI) -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI app with audit endpoints."""
    with TestClient(audit_app) as client:
        yield client
