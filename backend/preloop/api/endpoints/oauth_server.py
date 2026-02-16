"""OAuth Authorization Server endpoints for CLI and MCP client authentication.

Provides:
    GET  /oauth/authorize  — Redirects to the login/consent page
    POST /oauth/token      — Exchanges authorization code for tokens
    POST /oauth/register   — Dynamic client registration (MCP clients)
    POST /oauth/revoke     — Token revocation

The CLI uses /oauth/authorize + /oauth/token (no PKCE).
MCP clients (Claude Desktop) discover these via /.well-known metadata.
"""

import logging
import os
import time
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Query, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["OAuth Server"], include_in_schema=False)


# ---------------------------------------------------------------------------
# Well-known metadata endpoints (MCP OAuth discovery)
# ---------------------------------------------------------------------------


class AuthorizationServerMetadata(BaseModel):
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: Optional[str] = None
    revocation_endpoint: Optional[str] = None
    response_types_supported: list[str] = ["code"]
    grant_types_supported: list[str] = ["authorization_code", "refresh_token"]
    token_endpoint_auth_methods_supported: list[str] = ["client_secret_post", "none"]
    code_challenge_methods_supported: list[str] = ["S256"]


@router.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server_metadata():
    """Return OAuth Authorization Server Metadata (RFC 8414)."""
    base_url = os.getenv("PRELOOP_URL", "http://localhost:8000").rstrip("/")

    return AuthorizationServerMetadata(
        issuer=base_url,
        authorization_endpoint=f"{base_url}/oauth/authorize",
        token_endpoint=f"{base_url}/oauth/token",
        registration_endpoint=f"{base_url}/oauth/register",
        revocation_endpoint=f"{base_url}/oauth/revoke",
    )


@router.get("/.well-known/oauth-protected-resource/{path:path}")
async def oauth_protected_resource_metadata_with_path(path: str):
    """Return OAuth Protected Resource Metadata (RFC 9728) for a specific path.

    MCP clients look for this at:
      /.well-known/oauth-protected-resource/{mcp_server_path}
    e.g. /.well-known/oauth-protected-resource/mcp/v1
    """
    base_url = os.getenv("PRELOOP_URL", "http://localhost:8000").rstrip("/")

    return {
        "resource": f"{base_url}/{path}",
        "authorization_servers": [base_url],
    }


@router.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource_metadata():
    """Return OAuth Protected Resource Metadata (RFC 9728) for root."""
    base_url = os.getenv("PRELOOP_URL", "http://localhost:8000").rstrip("/")

    return {
        "resource": f"{base_url}/mcp",
        "authorization_servers": [base_url],
    }


# ---------------------------------------------------------------------------
# Authorization endpoint
# ---------------------------------------------------------------------------


@router.get("/oauth/authorize")
async def authorize(
    response_type: str = Query("code"),
    client_id: str = Query(""),
    redirect_uri: str = Query(...),
    state: str = Query(""),
    code_challenge: str = Query(""),
    code_challenge_method: str = Query(""),
    scope: str = Query(""),
):
    """OAuth authorization endpoint — redirects to the login/consent page.

    Both the CLI and MCP clients hit this endpoint. It redirects to the
    consent page where the user authenticates with their Preloop credentials.
    """
    # Use "cli" as default client_id for the CLI tool
    effective_client_id = client_id or "cli"

    # Build redirect to the consent page
    params = {
        "client_id": effective_client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scopes": scope,
        "redirect_uri_provided_explicitly": "true",
    }
    if code_challenge:
        params["code_challenge"] = code_challenge

    consent_url = f"/mcp/authorize/consent?{urlencode(params)}"
    return RedirectResponse(url=consent_url, status_code=302)


# ---------------------------------------------------------------------------
# Token endpoint
# ---------------------------------------------------------------------------


@router.post("/oauth/token")
async def token_exchange(
    grant_type: str = Form(...),
    code: str = Form(""),
    redirect_uri: str = Form(""),
    client_id: str = Form(""),
    client_secret: str = Form(""),
    code_verifier: str = Form(""),
    refresh_token: str = Form(""),
):
    """Exchange an authorization code for access/refresh tokens.

    Supports both:
    - CLI flow (no PKCE): returns JWT tokens usable with the REST API
    - MCP flow (with PKCE): returns opaque OAuth tokens
    """
    if grant_type == "authorization_code":
        return await _handle_authorization_code(
            code=code,
            redirect_uri=redirect_uri,
            client_id=client_id,
            code_verifier=code_verifier,
        )
    elif grant_type == "refresh_token":
        return await _handle_refresh_token(
            refresh_token_str=refresh_token,
            client_id=client_id,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported grant_type: {grant_type}",
        )


async def _handle_authorization_code(
    code: str, redirect_uri: str, client_id: str, code_verifier: str
):
    """Exchange authorization code for tokens."""
    from preloop.models.crud.oauth_mcp_token import crud_oauth_mcp_auth_code
    from preloop.models.db.session import get_db_session

    db = next(get_db_session())
    try:
        # Look up the auth code
        effective_client_id = client_id or "cli"
        db_code = crud_oauth_mcp_auth_code.get_by_code(
            db, code=code, client_id=effective_client_id
        )

        if not db_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid authorization code",
            )

        if db_code.is_used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authorization code already used",
            )

        if db_code.expires_at < time.time():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authorization code expired",
            )

        # Mark code as used
        crud_oauth_mcp_auth_code.mark_used(db, obj=db_code)

        # Decide token type based on whether PKCE was used
        has_pkce = bool(db_code.code_challenge)

        if has_pkce and code_verifier:
            # MCP flow: verify PKCE and issue opaque OAuth tokens
            import hashlib
            import base64

            expected = (
                base64.urlsafe_b64encode(
                    hashlib.sha256(code_verifier.encode()).digest()
                )
                .rstrip(b"=")
                .decode()
            )

            if expected != db_code.code_challenge:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid code_verifier (PKCE validation failed)",
                )

            return await _issue_opaque_tokens(db, db_code)
        else:
            # CLI flow: issue JWT tokens
            return await _issue_jwt_tokens(db, db_code)

    finally:
        db.close()


async def _issue_jwt_tokens(db, db_code):
    """Issue JWT access/refresh tokens for CLI usage."""
    from datetime import timedelta

    from preloop.api.auth.jwt import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
    from preloop.models.crud import crud_user

    user = crud_user.get(db, id=str(db_code.user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "scopes": []},
        expires_delta=access_token_expires,
    )

    refresh_token_expires = timedelta(days=7)
    refresh_token = create_access_token(
        data={"sub": str(user.id), "scopes": [], "refresh": True},
        expires_delta=refresh_token_expires,
    )

    return JSONResponse(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    )


async def _issue_opaque_tokens(db, db_code):
    """Issue opaque OAuth tokens for MCP clients."""
    from preloop.models.crud.oauth_mcp_token import (
        crud_oauth_mcp_access_token,
        crud_oauth_mcp_refresh_token,
        generate_token,
    )

    now = int(time.time())
    access_token_str = generate_token(32)
    refresh_token_str = generate_token(32)

    crud_oauth_mcp_access_token.create(
        db,
        token=access_token_str,
        client_id=db_code.client_id,
        user_id=db_code.user_id,
        account_id=db_code.account_id,
        scopes=db_code.scopes or [],
        expires_at=now + 3600,
        resource=db_code.resource,
    )

    crud_oauth_mcp_refresh_token.create(
        db,
        token=refresh_token_str,
        client_id=db_code.client_id,
        user_id=db_code.user_id,
        account_id=db_code.account_id,
        scopes=db_code.scopes or [],
        expires_at=now + 2592000,  # 30 days
    )

    return JSONResponse(
        {
            "access_token": access_token_str,
            "refresh_token": refresh_token_str,
            "token_type": "Bearer",
            "expires_in": 3600,
        }
    )


async def _handle_refresh_token(refresh_token_str: str, client_id: str):
    """Exchange a refresh token for new tokens."""
    from datetime import timedelta

    from preloop.api.auth.jwt import (
        create_access_token,
        decode_token,
        ACCESS_TOKEN_EXPIRE_MINUTES,
    )

    # Try JWT refresh token (the standard path for CLI)
    try:
        token_data = decode_token(refresh_token_str)
        if token_data.refresh and token_data.sub:
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": token_data.sub, "scopes": token_data.scopes or []},
                expires_delta=access_token_expires,
            )
            refresh_token_expires = timedelta(days=7)
            new_refresh = create_access_token(
                data={
                    "sub": token_data.sub,
                    "scopes": token_data.scopes or [],
                    "refresh": True,
                },
                expires_delta=refresh_token_expires,
            )
            return JSONResponse(
                {
                    "access_token": access_token,
                    "refresh_token": new_refresh,
                    "token_type": "bearer",
                    "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                }
            )
    except Exception:
        pass

    raise HTTPException(status_code=400, detail="Invalid refresh token")


# ---------------------------------------------------------------------------
# Dynamic Client Registration (for MCP clients)
# ---------------------------------------------------------------------------


@router.post("/oauth/register")
async def register_client(request_body: dict):
    """Register an OAuth client dynamically (RFC 7591).

    MCP clients (like Claude Desktop) call this to register before
    starting the authorization flow.
    """
    from preloop.api.endpoints.oauth_consent import get_oauth_provider

    provider = get_oauth_provider()
    if not provider:
        raise HTTPException(status_code=501, detail="OAuth not configured")

    from mcp.shared.auth import OAuthClientInformationFull

    client_info = OAuthClientInformationFull(
        client_id="pending",
        redirect_uris=request_body.get("redirect_uris", []),
        grant_types=request_body.get(
            "grant_types", ["authorization_code", "refresh_token"]
        ),
        response_types=request_body.get("response_types", ["code"]),
        token_endpoint_auth_method=request_body.get(
            "token_endpoint_auth_method", "none"
        ),
        client_name=request_body.get("client_name"),
        client_uri=request_body.get("client_uri"),
        scope=request_body.get("scope"),
        contacts=request_body.get("contacts"),
        software_id=request_body.get("software_id"),
        software_version=request_body.get("software_version"),
    )

    await provider.register_client(client_info)

    return JSONResponse(
        {
            "client_id": client_info.client_id,
            "client_secret": client_info.client_secret,
            "client_id_issued_at": client_info.client_id_issued_at,
            "client_secret_expires_at": client_info.client_secret_expires_at,
            "redirect_uris": [str(u) for u in (client_info.redirect_uris or [])],
            "grant_types": client_info.grant_types,
            "response_types": client_info.response_types,
            "token_endpoint_auth_method": client_info.token_endpoint_auth_method,
            "client_name": client_info.client_name,
        }
    )


# ---------------------------------------------------------------------------
# Token Revocation
# ---------------------------------------------------------------------------


@router.post("/oauth/revoke")
async def revoke_token(token: str = Form(...)):
    """Revoke an access or refresh token."""
    from preloop.api.endpoints.oauth_consent import get_oauth_provider

    provider = get_oauth_provider()
    if not provider:
        raise HTTPException(status_code=501, detail="OAuth not configured")

    # Try to load as access token first, then refresh token
    access_token = await provider.load_access_token(token)
    if access_token:
        await provider.revoke_token(access_token)
        return JSONResponse({"status": "revoked"})

    # Not found — still return success per RFC 7009
    return JSONResponse({"status": "revoked"})
