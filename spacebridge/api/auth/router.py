"""Authentication router for the API."""

from datetime import timedelta
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from spacebridge.api.auth.jwt import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    Token,
    User,
    create_access_token,
    get_current_active_user,
)

router = APIRouter()


@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> Dict[str, str]:
    """Login to get an access token.

    Args:
        form_data: OAuth2 password request form.

    Returns:
        Access token.

    Raises:
        HTTPException: If the username or password is incorrect.
    """
    # This is a simplified auth system for development
    # In a real application, you would check the credentials against a database

    # For now, hardcode a single user for development
    if form_data.username != "admin" or form_data.password != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token with user information
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": form_data.username, "scopes": form_data.scopes},
        expires_delta=access_token_expires,
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)) -> User:
    """Get the current user.

    Args:
        current_user: The current user.

    Returns:
        The current user.
    """
    return current_user
