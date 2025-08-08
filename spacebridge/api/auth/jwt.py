"""Authentication for the API, including JWT tokens and API keys."""

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.future import select

from spacebridge.schemas.auth import TokenData
from spacemodels.db.session import get_db_session
from spacemodels.models.account import Account
from spacemodels.models.api_key import ApiKey

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "development_secret_key_do_not_use_in_production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# Password context for hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/token", auto_error=False
)

# Logger
logger = logging.getLogger(__name__)


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
        refresh = payload.get("refresh", False)

        return TokenData(
            sub=sub,
            scopes=scopes,
            exp=datetime.fromtimestamp(exp) if exp else None,
            refresh=refresh,
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Account:
    """Get the current user from a JWT token or API key.

    Args:
        token: JWT token or API key.

    Returns:
        The current user.

    Raises:
        HTTPException: If the token is invalid or the user doesn't exist.
    """
    logger.info(f"Authenticating token: {token[:10]}...")
    # If token looks like an API key (no periods, which JWT has), try API key first
    # Most API keys are random alphanumeric strings without dots
    if token and "." not in token:
        logger.info(
            "Token appears to be an API key (no . character), trying API key authentication first"
        )
        try:
            session_generator = get_db_session()
            session = next(session_generator)

            try:
                # Look up the API key
                logger.info(f"Looking up API key: {token[:10]}...")
                result = session.execute(select(ApiKey).where(ApiKey.key == token))
                api_key = result.scalars().first()

                if api_key:
                    logger.info(
                        f"API key found: {api_key.name}, created by: {api_key.created_by}"
                    )

                    # Check if the API key has expired
                    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
                        logger.warning(f"API key expired: {api_key.expires_at}")
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="API key has expired",
                            headers={"WWW-Authenticate": "Bearer"},
                        )

                    # Get the user associated with this API key
                    result = session.execute(
                        select(Account).where(Account.username == api_key.created_by)
                    )
                    user = result.scalars().first()

                    if not user:
                        logger.warning(
                            f"User not found for API key: {api_key.created_by}"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="User associated with API key not found",
                            headers={"WWW-Authenticate": "Bearer"},
                        )

                    if not user.is_active:
                        logger.warning(
                            f"Inactive user for API key: {api_key.created_by}"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Inactive user",
                            headers={"WWW-Authenticate": "Bearer"},
                        )

                    # Update the last_used_at timestamp
                    api_key.last_used_at = datetime.utcnow()
                    session.add(api_key)
                    session.commit()

                    logger.info(
                        f"API key authentication successful for user: {user.username}"
                    )
                    return user  # Return the full Account object
            finally:
                session.close()
                try:
                    # Clean up the generator
                    next(session_generator, None)
                except StopIteration:
                    pass
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Error in API key first-try authentication: {str(e)}")
            # Fall through to JWT authentication
            logger.info("API key authentication failed, falling back to JWT")

    # Try to authenticate with JWT token
    try:
        # Try to decode as JWT token
        logger.info("Attempting JWT authentication")
        token_data = decode_token(token)
        logger.info(f"JWT decoded successfully: {token_data}")

        # Check if it's a refresh token
        if isinstance(token_data, dict) and token_data.get("refresh", False):
            logger.warning("Attempted to use refresh token for authentication")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Cannot use refresh token for authentication",
                headers={"WWW-Authenticate": "Bearer"},
            )

        username = getattr(token_data, "sub", "")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get user from database
        try:
            session_generator = get_db_session()
            session = next(session_generator)

            try:
                result = session.execute(
                    select(Account).where(Account.username == username)
                )
                user = result.scalars().first()

                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User not found",
                        headers={"WWW-Authenticate": "Bearer"},
                    )

                if not user.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Inactive user",
                        headers={"WWW-Authenticate": "Bearer"},
                    )

                return user  # Return the full Account object
            finally:
                session.close()
                try:
                    # Clean up the generator
                    next(session_generator, None)
                except StopIteration:
                    pass
        except Exception as e:
            logger.error(f"Error getting current user from JWT: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication error",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError as e:
        # If JWT decoding fails and we haven't tried API key authentication yet, try it
        if (
            "." in token
        ):  # Only try API key auth if we haven't already (tokens with dots were tried as JWT first)
            logger.info(
                f"JWT authentication failed: {str(e)}, attempting API key authentication as fallback"
            )
            try:
                session_generator = get_db_session()
                session = next(session_generator)

                try:
                    # Look up the API key
                    logger.info(f"Looking up API key: {token[:10]}...")
                    result = session.execute(select(ApiKey).where(ApiKey.key == token))
                    api_key = result.scalars().first()

                    if not api_key:
                        logger.warning(f"API key not found: {token[:10]}...")
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid API key",
                            headers={"WWW-Authenticate": "Bearer"},
                        )

                    logger.info(
                        f"API key found: {api_key.name}, created by: {api_key.created_by}"
                    )

                    # Check if the API key has expired
                    if api_key.expires_at and api_key.expires_at < datetime.utcnow():
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="API key has expired",
                            headers={"WWW-Authenticate": "Bearer"},
                        )

                    # Get the user associated with this API key
                    result = session.execute(
                        select(Account).where(Account.username == api_key.created_by)
                    )
                    user = result.scalars().first()

                    if not user:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="User associated with API key not found",
                            headers={"WWW-Authenticate": "Bearer"},
                        )

                    if not user.is_active:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Inactive user",
                            headers={"WWW-Authenticate": "Bearer"},
                        )

                    # Update the last_used_at timestamp
                    api_key.last_used_at = datetime.utcnow()
                    session.add(api_key)
                    session.commit()

                    logger.info(
                        f"API key authentication successful for user: {user.username}"
                    )
                    return user  # Return the full Account object
                finally:
                    session.close()
                    try:
                        # Clean up the generator
                        next(session_generator, None)
                    except StopIteration:
                        pass
            except HTTPException:
                # Re-raise HTTP exceptions
                raise
            except Exception as e:
                logger.error(f"Error authenticating with API key: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication error",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            # We already tried API key authentication first for tokens without dots
            logger.error("Both JWT and API key authentication methods failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )


async def get_current_active_user(
    current_user: Account = Depends(get_current_user),
) -> Account:
    """Get the current active user.

    Args:
        current_user: The current user.

    Returns:
        The current active user.

    Raises:
        HTTPException: If the user is disabled.
    """
    # Disabled check is now handled in get_current_user
    return current_user


async def get_current_active_user_optional(
    token: str = Depends(oauth2_scheme_optional),
) -> Optional[Account]:
    """
    Get the current active user if a valid token is provided, otherwise return None.
    This dependency will not raise an error if the token is missing or invalid.
    """
    if token is None:
        return None
    try:
        # We must call get_current_user with the token parameter, not as a dependency,
        # to bypass the strict oauth2_scheme it depends on.
        user = await get_current_user(token=token)
        if user and user.is_active:
            return user
        return None
    except HTTPException:
        # Any authentication error (invalid, expired, etc.) should result in None
        return None


async def get_user_from_token_if_valid(
    token: str, db_session: Any
) -> Optional[Account]:
    """
    Manually attempts to retrieve a user from a token string.
    Returns None if the token is invalid, expired, or the user doesn't exist.
    This function does not raise HTTPException.
    """
    if not token:
        return None
    try:
        # The get_current_user function contains all the necessary logic
        # for decoding JWTs, checking API keys, and verifying the user.
        # We call it directly with the token.
        user = await get_current_user(token=token)
        return user
    except Exception:
        # If any exception occurs during authentication, we simply return None.
        return None
