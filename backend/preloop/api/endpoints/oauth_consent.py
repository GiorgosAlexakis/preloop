"""OAuth consent page handler for MCP OAuth authorization flow.

This module provides the login/consent endpoints that are displayed to the user
during the OAuth authorization code flow. The MCP OAuth AS redirects the user
here, they log in with their Preloop credentials, and are redirected back to
the MCP client with an authorization code.

Routes:
    GET  /mcp/authorize/consent  - Renders the login/consent form
    POST /mcp/authorize/consent  - Authenticates user and issues auth code
"""

import html
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


# Known CLI client_id — allowed to use http://localhost redirect URIs
_CLI_CLIENT_ID = "cli"


def _render_template(template_name: str, context: dict) -> str:
    """Template rendering with auto HTML-escaping for XSS prevention.

    Uses Jinja2-style {{ variable }} placeholders.
    All values are HTML-escaped to prevent XSS attacks from user-controlled
    inputs (client_name, redirect_uri, state, error, etc.).

    Values under keys ending with '_json' are JSON-encoded (for <script> blocks)
    instead of HTML-escaped.
    """
    template_path = _TEMPLATE_DIR / template_name
    template = template_path.read_text()

    for key, value in context.items():
        safe_value = html.escape(str(value or ""))
        template = template.replace("{{ " + key + " }}", safe_value)

    return template


def _validate_client_and_redirect(client_id: str, redirect_uri: str) -> dict:
    """Validate that client_id exists and redirect_uri is registered.

    Returns dict with 'error' (str or None) and 'client_name'.
    """
    from preloop.models.crud.oauth_mcp_client import crud_oauth_mcp_client

    # CLI client gets special treatment — allow localhost redirects
    if client_id == _CLI_CLIENT_ID:
        from urllib.parse import urlparse

        parsed = urlparse(redirect_uri)
        if parsed.hostname not in ("localhost", "127.0.0.1", "[::1]"):
            return {
                "error": "Invalid redirect_uri for CLI client (must be localhost)",
                "client_name": "CLI",
            }
        return {"error": None, "client_name": "Preloop CLI"}

    # Look up registered client
    db = next(get_db_session())
    try:
        db_client = crud_oauth_mcp_client.get_by_client_id(db, client_id=client_id)
        if not db_client:
            logger.warning(f"OAuth consent: unknown client_id={client_id}")
            return {"error": "Unknown client_id", "client_name": ""}

        client_name = db_client.client_name or "MCP Client"

        # Verify redirect_uri is registered for this client
        registered_uris = db_client.redirect_uris or []
        if redirect_uri not in registered_uris:
            logger.warning(
                f"OAuth consent: unregistered redirect_uri={redirect_uri} "
                f"for client_id={client_id}"
            )
            return {
                "error": "redirect_uri is not registered for this client",
                "client_name": client_name,
            }

        return {"error": None, "client_name": client_name}
    except Exception as e:
        logger.error(f"OAuth consent validation error: {e}", exc_info=True)
        return {"error": "Internal error validating client", "client_name": ""}
    finally:
        db.close()


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
    # Validate client_id and redirect_uri
    validation = _validate_client_and_redirect(client_id, redirect_uri)
    if validation["error"]:
        return HTMLResponse(
            content=f"<h1>OAuth Error</h1><p>{html.escape(validation['error'])}</p>",
            status_code=400,
        )
    client_name = validation["client_name"]

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

    html_content = _render_template("oauth_authorize.html", context)
    return HTMLResponse(content=html_content)


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

    # Re-validate client_id + redirect_uri on POST (defense in depth)
    validation = _validate_client_and_redirect(client_id, redirect_uri)
    if validation["error"]:
        return HTMLResponse(
            content=f"<h1>OAuth Error</h1><p>{html.escape(validation['error'])}</p>",
            status_code=400,
        )

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
    html_content = _render_template("oauth_authorize.html", context)
    return HTMLResponse(content=html_content)


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
