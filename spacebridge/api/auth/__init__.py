"""Authentication package for the API."""

from spacebridge.api.auth.jwt import (
    get_current_active_user,
    get_current_user,
    get_current_active_user_optional,  # Added optional user getter
    oauth2_scheme,
)
from spacebridge.api.auth.router import router as auth_router

__all__ = [
    "auth_router",
    "get_current_user",
    "get_current_active_user",
    "oauth2_scheme",
    "get_current_active_user_optional",  # Added optional user getter
]
