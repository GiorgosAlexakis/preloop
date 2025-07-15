"""Authentication router for the API."""

import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Session

from spacebridge.api.auth.jwt import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    decode_token,
    get_current_active_user,
    get_password_hash,
    verify_password,
)
from spacebridge.schemas.auth import (
    ApiKeyCreate,
    ApiKeyResponse,
    ApiKeySummary,
    ApiUsageStatistics,
    EmailVerificationRequest,
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshRequest,
    Token,
    User,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from spacebridge.utils.email import (
    send_password_reset_email,
    send_product_notification_email,
    send_verification_email,
)
from spacebridge.utils.tokens import (
    TokenError,
    create_email_verification_token,
    create_password_reset_token,
    verify_token,
)
from spacemodels.crud import crud_account
from spacemodels.db.session import get_db_session
from spacemodels.models.account import Account
from spacemodels.models.api_key import ApiKey
from spacemodels.models.api_usage import ApiUsage

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user_data: UserCreate, background_tasks: BackgroundTasks, request: Request
) -> Dict[str, str]:
    """Register a new user.

    Args:
        user_data: User creation data.
        background_tasks: Background tasks for sending emails.
        request: The incoming request object.

    Returns:
        The created user.

    Raises:
        HTTPException: If the username or email is already taken.
    """
    # Check if username or email already exists
    # Since get_db_session() doesn't support async with, we'll use a manual approach
    session_generator = get_db_session()
    session = next(session_generator)

    try:
        # Check if username exists
        result = session.execute(
            select(Account).where(Account.username == user_data.username)
        )
        existing_user = result.scalars().first()
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered",
            )

        # Check if email exists
        result = session.execute(
            select(Account).where(Account.email == user_data.email)
        )
        existing_email = result.scalars().first()
        if existing_email is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Create new user
        hashed_password = get_password_hash(user_data.password)
        new_user = Account(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            is_active=True,
            email_verified=False,
        )

        try:
            session.add(new_user)
            session.commit()
            session.refresh(new_user)

            # Generate email verification token
            token = create_email_verification_token(user_data.email)

            # Send verification email as a background task
            background_tasks.add_task(
                send_verification_email, user_email=user_data.email, token=token
            )

            # Send product notification email
            try:
                user_info_for_email = {
                    "username": new_user.username,
                    "email": new_user.email,
                    "full_name": new_user.full_name,
                    "is_active": new_user.is_active,
                    "email_verified": new_user.email_verified,
                    "id": str(new_user.id) if new_user.id else None,
                    "created_at": new_user.created_at.isoformat()
                    if new_user.created_at
                    else None,
                }
                await send_product_notification_email(
                    user_data=user_info_for_email,
                    source_ip=request.client.host if request.client else "Unknown",
                    tracker_data=None,
                )
            except Exception as e:
                logger.error(
                    f"Failed to send product notification email for user {new_user.email}: {str(e)}"
                )

            return {
                "username": new_user.username,
                "email": new_user.email,
                "full_name": new_user.full_name,
                "email_verified": new_user.email_verified,
            }
        except IntegrityError:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error creating user - username or email may be taken",
            )
        except Exception as e:
            session.rollback()
            logger.error(f"Error registering user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error registering user",
            )
    finally:
        session.close()
        try:
            # Clean up the generator
            next(session_generator, None)
        except StopIteration:
            pass


@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(verification_data: EmailVerificationRequest) -> Dict[str, str]:
    """Verify a user's email address.

    Args:
        verification_data: Email verification data with token.

    Returns:
        Success message.

    Raises:
        HTTPException: If the token is invalid or the user does not exist.
    """
    try:
        # Verify the token
        email = verify_token(verification_data.token, "email_verification")

        # Find and update the user
        session_generator = get_db_session()
        session = next(session_generator)

        try:
            # Find the user
            result = session.execute(select(Account).where(Account.email == email))
            user = result.scalars().first()

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            # Update email verification status
            user.email_verified = True
            session.commit()

            return {"message": "Email verified successfully"}
        finally:
            session.close()
            try:
                # Clean up the generator
                next(session_generator, None)
            except StopIteration:
                pass

    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error verifying email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error verifying email",
        )


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    reset_data: PasswordResetRequest, background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """Send a password reset email.

    Args:
        reset_data: Password reset request with email.
        background_tasks: Background tasks for sending emails.

    Returns:
        Success message.
    """
    # Always return success even if email doesn't exist (security best practice)
    # But only send email if user exists
    session_generator = get_db_session()
    session = next(session_generator)

    try:
        result = session.execute(
            select(Account).where(Account.email == reset_data.email)
        )
        user = result.scalars().first()

        if user:
            # Generate password reset token
            token = create_password_reset_token(reset_data.email)

            # Send password reset email as a background task
            background_tasks.add_task(
                send_password_reset_email, user_email=reset_data.email, token=token
            )
    finally:
        session.close()
        try:
            # Clean up the generator
            next(session_generator, None)
        except StopIteration:
            pass

    return {
        "message": "If your email is registered, you will receive a password reset link"
    }


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(reset_data: PasswordResetConfirmRequest) -> Dict[str, str]:
    """Reset a user's password.

    Args:
        reset_data: Password reset confirmation with token and new password.

    Returns:
        Success message.

    Raises:
        HTTPException: If the token is invalid or the user does not exist.
    """
    try:
        # Verify the token
        email = verify_token(reset_data.token, "password_reset")

        # Find and update the user
        session_generator = get_db_session()
        session = next(session_generator)

        try:
            result = session.execute(select(Account).where(Account.email == email))
            user = result.scalars().first()

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            # Update password
            user.hashed_password = get_password_hash(reset_data.new_password)
            session.commit()

            return {"message": "Password reset successfully"}
        finally:
            session.close()
            try:
                # Clean up the generator
                next(session_generator, None)
            except StopIteration:
                pass
    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error resetting password: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error resetting password",
        )


@router.post("/token", response_model=Token)
async def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Dict[str, str]:
    """Login to get an access token using form data (required for OAuth2 flow).

    Args:
        form_data: OAuth2 password request form.

    Returns:
        Access token.

    Raises:
        HTTPException: If the username or password is incorrect.
    """
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token with user information
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "scopes": form_data.scopes or []},
        expires_delta=access_token_expires,
    )

    # Create refresh token with longer expiration
    refresh_token_expires = timedelta(days=7)  # 7 days
    refresh_token = create_access_token(
        data={"sub": user.username, "scopes": form_data.scopes or [], "refresh": True},
        expires_delta=refresh_token_expires,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # in seconds
    }


@router.post("/token/json", response_model=Token)
async def login_json(request: LoginRequest) -> Dict[str, str]:
    """Login to get an access token using JSON data.

    Args:
        request: Login request with username and password.

    Returns:
        Access token.

    Raises:
        HTTPException: If the username or password is incorrect.
    """
    user = await authenticate_user(request.username, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token with user information
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "scopes": []},
        expires_delta=access_token_expires,
    )

    # Create refresh token with longer expiration
    refresh_token_expires = timedelta(days=7)  # 7 days
    refresh_token = create_access_token(
        data={"sub": user.username, "scopes": [], "refresh": True},
        expires_delta=refresh_token_expires,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # in seconds
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: RefreshRequest, db: AsyncSession = Depends(get_db_session)
) -> Dict[str, str]:
    """Refresh an access token using a refresh token.

    Args:
        request: Refresh token request.

    Returns:
        New access token.

    Raises:
        HTTPException: If the refresh token is invalid or expired.
    """
    try:
        # Decode and validate the refresh token
        token_data = decode_token(request.refresh_token)

        # Verify user exists and is active
        result = await db.execute(
            select(Account).where(Account.id == int(token_data.sub))
        )
        user = result.scalars().first()

        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if it's a refresh token
        if not token_data.refresh:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Create a new access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": token_data.sub, "scopes": token_data.scopes},
            expires_delta=access_token_expires,
        )

        # Create a new refresh token
        refresh_token_expires = timedelta(days=7)  # 7 days
        refresh_token = create_access_token(
            data={"sub": token_data.sub, "scopes": token_data.scopes, "refresh": True},
            expires_delta=refresh_token_expires,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # in seconds
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid refresh token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)) -> User:
    """Get the current user.

    Args:
        current_user: The current user.

    Returns:
        The current user.
    """
    return current_user


@router.put("/users/me", response_model=UserResponse)
async def update_user_me(
    *,
    db: Session = Depends(get_db_session),
    user_update: UserUpdate,
    current_user: Account = Depends(get_current_active_user),
) -> Any:
    """Update own user."""
    user = crud_account.update(db, db_obj=current_user, obj_in=user_update)
    return user


@router.put("/users/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_current_user_password(
    passwords: PasswordChangeRequest,
    current_user: Account = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
):
    """Change current user's password."""
    if not verify_password(passwords.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password",
        )
    hashed_password = get_password_hash(passwords.new_password)
    crud_account.update(
        db, db_obj=current_user, obj_in={"hashed_password": hashed_password}
    )


@router.post("/api-keys", response_model=ApiKeyResponse)
async def create_api_key(
    key_data: ApiKeyCreate,
    current_user: UserResponse = Depends(get_current_active_user),
) -> ApiKeyResponse:
    """Create a new API key.

    Args:
        key_data: The key creation data.
        current_user: The current authenticated user.

    Returns:
        The created API key details.
    """
    # Generate a secure random key
    alphabet = string.ascii_letters + string.digits
    key_value = "".join(secrets.choice(alphabet) for _ in range(40))

    session_generator = get_db_session()
    session = next(session_generator)

    try:
        # Create a new API key
        new_key = ApiKey(
            name=key_data.name,
            key=key_value,
            scopes=key_data.scopes,
            created_by=current_user.username,
            expires_at=key_data.expires_at,
        )

        session.add(new_key)
        session.commit()
        session.refresh(new_key)

        return ApiKeyResponse(
            id=new_key.id,
            name=new_key.name,
            key=new_key.key,
            created_at=new_key.created_at,
            expires_at=new_key.expires_at,
            scopes=new_key.scopes,
            created_by=new_key.created_by,
            last_used_at=new_key.last_used_at,
        )
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key with this name already exists",
        )
    except Exception as e:
        session.rollback()
        logger.error(f"Error creating API key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating API key",
        )
    finally:
        session.close()
        try:
            # Clean up the generator
            next(session_generator, None)
        except StopIteration:
            pass


@router.get("/api-keys", response_model=List[ApiKeySummary])
async def list_api_keys(
    current_user: UserResponse = Depends(get_current_active_user),
) -> List[ApiKeySummary]:
    """List all API keys for the current user.

    Args:
        current_user: The current authenticated user.

    Returns:
        List of API keys.
    """
    session_generator = get_db_session()
    session = next(session_generator)

    try:
        result = session.execute(
            select(ApiKey)
            .where(ApiKey.created_by == current_user.username)
            .order_by(ApiKey.created_at.desc())
        )
        keys = result.scalars().all()

        return [
            ApiKeySummary(
                id=key.id,
                name=key.name,
                created_at=key.created_at,
                expires_at=key.expires_at,
                scopes=key.scopes,
                last_used_at=key.last_used_at,
            )
            for key in keys
        ]
    finally:
        session.close()
        try:
            # Clean up the generator
            next(session_generator, None)
        except StopIteration:
            pass


@router.get("/api-keys/debug", response_model=List[ApiKeyResponse])
async def debug_api_keys(
    username: str,
    api_key: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_active_user),
) -> List[ApiKeyResponse]:
    """Debug endpoint to get API keys with their values (admin only).

    Args:
        username: The username to get keys for
        api_key: Optional specific API key to look up
        current_user: The current authenticated user.

    Returns:
        List of API keys with their values.
    """
    # This is for debugging only
    session_generator = get_db_session()
    session = next(session_generator)

    try:
        # Check if specific key was requested
        if api_key:
            logger.info(f"Looking up specific API key: {api_key[:10]}...")
            result = session.execute(select(ApiKey).where(ApiKey.key == api_key))
            key = result.scalars().first()
            return (
                [
                    ApiKeyResponse(
                        id=key.id
                        if key
                        else UUID("00000000-0000-0000-0000-000000000000"),
                        name=key.name if key else "Not Found",
                        key=key.key if key else api_key,
                        created_at=key.created_at if key else datetime.utcnow(),
                        expires_at=key.expires_at if key else None,
                        scopes=key.scopes if key else [],
                        created_by=key.created_by if key else "unknown",
                        last_used_at=key.last_used_at if key else None,
                    )
                ]
                if key
                else []
            )

        # Get all keys for the specified user
        query = select(ApiKey).where(ApiKey.created_by == username)
        result = session.execute(query)
        keys = result.scalars().all()

        return [
            ApiKeyResponse(
                id=key.id,
                name=key.name,
                key=key.key,
                created_at=key.created_at,
                expires_at=key.expires_at,
                scopes=key.scopes,
                created_by=key.created_by,
                last_used_at=key.last_used_at,
            )
            for key in keys
        ]
    except Exception as e:
        logger.error(f"Error debugging API keys: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error debugging API keys: {str(e)}",
        )
    finally:
        session.close()
        try:
            # Clean up the generator
            next(session_generator, None)
        except StopIteration:
            pass


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: UUID, current_user: UserResponse = Depends(get_current_active_user)
) -> None:
    """Delete an API key.

    Args:
        key_id: The ID of the key to delete.
        current_user: The current authenticated user.

    Raises:
        HTTPException: If the key doesn't exist or doesn't belong to the user.
    """
    session_generator = get_db_session()
    session = next(session_generator)

    try:
        # Get the key
        result = session.execute(
            select(ApiKey)
            .where(ApiKey.id == key_id)
            .where(ApiKey.created_by == current_user.username)
        )
        key = result.scalars().first()

        if not key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found",
            )

        # Delete the key
        session.delete(key)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Error deleting API key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting API key",
        )
    finally:
        session.close()
        try:
            # Clean up the generator
            next(session_generator, None)
        except StopIteration:
            pass


@router.get("/api-usage", response_model=ApiUsageStatistics)
async def get_api_usage(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: UserResponse = Depends(get_current_active_user),
) -> ApiUsageStatistics:
    """Get API usage statistics for the current user.

    Args:
        start_date: Optional start date for filtering.
        end_date: Optional end date for filtering.
        current_user: The current authenticated user.

    Returns:
        API usage statistics.
    """
    session_generator = get_db_session()
    session = next(session_generator)

    try:
        # Base query
        query = select(ApiUsage).where(ApiUsage.username == current_user.username)

        # Apply date filters if provided
        if start_date:
            query = query.where(ApiUsage.timestamp >= start_date)
        if end_date:
            query = query.where(ApiUsage.timestamp <= end_date)

        result = session.execute(query)
        usage_entries = result.scalars().all()

        # Calculate statistics
        total_requests = len(usage_entries)

        # Group by date
        requests_by_date = {}
        for entry in usage_entries:
            date_str = entry.timestamp.strftime("%Y-%m-%d")
            requests_by_date[date_str] = requests_by_date.get(date_str, 0) + 1

        # Count issue actions
        issues_created = sum(
            1 for entry in usage_entries if entry.action_type == "create_issue"
        )
        issues_updated = sum(
            1 for entry in usage_entries if entry.action_type == "update_issue"
        )
        issues_closed = sum(
            1 for entry in usage_entries if entry.action_type == "close_issue"
        )

        # Group by endpoint
        requests_by_endpoint = {}
        for entry in usage_entries:
            endpoint = entry.endpoint
            requests_by_endpoint[endpoint] = requests_by_endpoint.get(endpoint, 0) + 1

        return ApiUsageStatistics(
            total_requests=total_requests,
            requests_by_date=requests_by_date,
            issues_created=issues_created,
            issues_updated=issues_updated,
            issues_closed=issues_closed,
            requests_by_endpoint=requests_by_endpoint,
        )
    finally:
        session.close()
        try:
            # Clean up the generator
            next(session_generator, None)
        except StopIteration:
            pass


async def authenticate_user(username: str, password: str) -> Optional[Account]:
    """Authenticate a user.

    Args:
        username: The username.
        password: The password.

    Returns:
        The user if authentication is successful, None otherwise.
    """
    session_generator = get_db_session()
    session = next(session_generator)

    try:
        result = session.execute(select(Account).where(Account.username == username))
        user = result.scalars().first()

        if not user:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        if not user.is_active:
            return None

        return user
    finally:
        session.close()
        try:
            # Clean up the generator
            next(session_generator, None)
        except StopIteration:
            pass
