"""JWT authentication for the API."""

import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "development_secret_key_do_not_use_in_production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Password context for hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token")


class Token(BaseModel):
    """Token response model."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token data model."""

    sub: Optional[str] = None
    scopes: list[str] = []
    exp: Optional[datetime] = None


class User(BaseModel):
    """User model."""

    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None


class UserInDB(User):
    """User in database model."""

    hashed_password: str


def get_password_hash(password: str) -> str:
    """Hash a password.

    Args:
        password: Plain text password.

    Returns:
        Hashed password.
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash.

    Args:
        plain_password: Plain text password.
        hashed_password: Hashed password.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token.

    Args:
        data: Data to encode in the token.
        expires_delta: Token expiration time delta.

    Returns:
        JWT access token.
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenData:
    """Decode a JWT token.

    Args:
        token: JWT token.

    Returns:
        Decoded token data.

    Raises:
        HTTPException: If the token is invalid.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        sub: str = payload.get("sub", "")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        scopes = payload.get("scopes", [])
        exp = payload.get("exp")

        return TokenData(sub=sub, scopes=scopes, exp=exp)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Get the current user from a JWT token.

    Args:
        token: JWT token.

    Returns:
        The current user.

    Raises:
        HTTPException: If the token is invalid or the user doesn't exist.
    """
    token_data = decode_token(token)

    # In a real application, you would query the database for the user
    # For now, we'll just return a hardcoded user for development
    if token_data.sub != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return User(
        username="admin",
        email="admin@example.com",
        full_name="Admin User",
        disabled=False,
    )


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get the current active user.

    Args:
        current_user: The current user.

    Returns:
        The current active user.

    Raises:
        HTTPException: If the user is disabled.
    """
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
