"""OAuth consent page handler for MCP OAuth authorization flow.

This module provides the login/consent endpoints that are displayed to the user
during the OAuth authorization code flow. The MCP OAuth AS redirects the user
here, they log in with their Preloop credentials, and are redirected back to
the MCP client with an authorization code.

Routes:
    GET  /mcp/authorize/consent  - Renders the login/consent form
    POST /mcp/authorize/consent  - Authenticates user and issues auth code
"""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from mcp.server.auth.provider import construct_redirect_uri

from preloop.models.db.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["OAuth Consent"], include_in_schema=False)

# Template directory
_TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"


def _render_template(template_name: str, context: dict) -> str:
    """Simple template rendering using string replacement.

    Uses Jinja2-style {{ variable }} placeholders.
    """
    template_path = _TEMPLATE_DIR / template_name
    template = template_path.read_text()

    for key, value in context.items():
        template = template.replace("{{ " + key + " }}", str(value or ""))

    return template


@router.get("/mcp/authorize/consent")
async def consent_page(
    client_id: str,
    redirect_uri: str,
    code_challenge: str = "",
    state: str = "",
    scopes: str = "",
    redirect_uri_provided_explicitly: str = "true",
    resource: str = "",
):
    """Render the OAuth login/consent page.

    This page is shown to the user when an MCP client initiates an OAuth
    authorization flow. The user must enter their Preloop credentials to
    approve the authorization.
    """
    # Look up client name for display
    client_name = "MCP Client"
    try:
        from preloop.models.crud.oauth_mcp_client import crud_oauth_mcp_client

        db = next(get_db_session())
        try:
            db_client = crud_oauth_mcp_client.get_by_client_id(db, client_id=client_id)
            if db_client and db_client.client_name:
                client_name = db_client.client_name
        finally:
            db.close()
    except Exception:
        pass

    context = {
        "client_id": client_id,
        "client_name": client_name,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "state": state,
        "scopes": scopes,
        "redirect_uri_provided_explicitly": redirect_uri_provided_explicitly,
        "resource": resource,
        "error": "",
    }

    html = _render_template("oauth_authorize.html", context)
    return HTMLResponse(content=html)


@router.post("/mcp/authorize/consent")
async def consent_submit(
    client_id: str = Form(...),
    redirect_uri: str = Form(...),
    code_challenge: str = Form(""),
    state: str = Form(""),
    scopes: str = Form(""),
    redirect_uri_provided_explicitly: str = Form("true"),
    resource: str = Form(""),
    username: str = Form(...),
    password: str = Form(...),
):
    """Handle login form submission and issue an authorization code.

    Authenticates the user with their Preloop credentials, creates an
    authorization code, and redirects back to the MCP client.
    """
    from preloop.api.auth.jwt import verify_password
    from preloop.models.crud import crud_user

    db = next(get_db_session())
    try:
        # Authenticate user — try username first, then email
        user = crud_user.get_by_username(db, username=username)
        if not user:
            user = crud_user.get_by_email(db, email=username)
        if not user or not user.hashed_password:
            return _render_error_response(
                "Invalid username or password",
                client_id=client_id,
                redirect_uri=redirect_uri,
                code_challenge=code_challenge,
                state=state,
                scopes=scopes,
                redirect_uri_provided_explicitly=redirect_uri_provided_explicitly,
                resource=resource,
            )

        if not verify_password(password, user.hashed_password):
            return _render_error_response(
                "Invalid username or password",
                client_id=client_id,
                redirect_uri=redirect_uri,
                code_challenge=code_challenge,
                state=state,
                scopes=scopes,
                redirect_uri_provided_explicitly=redirect_uri_provided_explicitly,
                resource=resource,
            )

        if not user.is_active:
            return _render_error_response(
                "Account is deactivated",
                client_id=client_id,
                redirect_uri=redirect_uri,
                code_challenge=code_challenge,
                state=state,
                scopes=scopes,
                redirect_uri_provided_explicitly=redirect_uri_provided_explicitly,
                resource=resource,
            )

        # Get the OAuth provider instance
        provider = _get_oauth_provider()
        if not provider:
            return _render_error_response(
                "OAuth not configured",
                client_id=client_id,
                redirect_uri=redirect_uri,
                code_challenge=code_challenge,
                state=state,
                scopes=scopes,
                redirect_uri_provided_explicitly=redirect_uri_provided_explicitly,
                resource=resource,
            )

        # Create authorization code
        scope_list = scopes.split() if scopes else []
        code = provider.create_authorization_code_for_user(
            client_id=client_id,
            user_id=user.id,
            account_id=user.account_id,
            redirect_uri=redirect_uri,
            redirect_uri_provided_explicitly=(
                redirect_uri_provided_explicitly == "true"
            ),
            code_challenge=code_challenge,
            scopes=scope_list,
            resource=resource or None,
        )

        # Redirect back to client with authorization code
        redirect_url = construct_redirect_uri(
            redirect_uri,
            code=code,
            state=state if state else None,
        )

        logger.info(f"OAuth consent granted: user={user.username}, client={client_id}")

        return RedirectResponse(url=redirect_url, status_code=302)

    finally:
        db.close()


def _render_error_response(
    error: str,
    *,
    client_id: str,
    redirect_uri: str,
    code_challenge: str,
    state: str,
    scopes: str,
    redirect_uri_provided_explicitly: str,
    resource: str,
) -> HTMLResponse:
    """Re-render the consent page with an error message."""
    context = {
        "client_id": client_id,
        "client_name": "MCP Client",
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "state": state,
        "scopes": scopes,
        "redirect_uri_provided_explicitly": redirect_uri_provided_explicitly,
        "resource": resource,
        "error": error,
    }
    html = _render_template("oauth_authorize.html", context)
    return HTMLResponse(content=html)


# Singleton provider instance
_oauth_provider_instance = None


def _get_oauth_provider():
    """Get the shared PreloopOAuthProvider instance."""
    global _oauth_provider_instance
    if _oauth_provider_instance is None:
        from preloop.services.oauth_provider import PreloopOAuthProvider

        base_url = os.getenv("PRELOOP_URL", "http://localhost:8000")
        _oauth_provider_instance = PreloopOAuthProvider(
            base_url=f"{base_url.rstrip('/')}/mcp",
            issuer_url=f"{base_url.rstrip('/')}/mcp",
        )
    return _oauth_provider_instance


def get_oauth_provider():
    """Public accessor for the shared OAuth provider instance."""
    return _get_oauth_provider()
