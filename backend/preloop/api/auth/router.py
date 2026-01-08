"""Authentication router for the API."""

import logging
import secrets
import string
from datetime import datetime, timedelta, UTC
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
from sqlalchemy.orm import Session

from preloop.api.auth.jwt import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    decode_token,
    get_current_active_user,
    get_password_hash,
    verify_password,
)
from preloop.config import settings
from preloop.schemas.auth import (
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
    AuthUserCreate,
    AuthUserResponse,
    AuthUserUpdate,
)
from preloop.utils import get_client_ip
from preloop.utils.email import (
    send_password_reset_email,
    send_product_notification_email,
    send_verification_email,
)
from preloop.utils.tokens import (
    TokenError,
    create_email_verification_token,
    create_password_reset_token,
    verify_token,
)
from preloop.models.crud import (
    crud_account,
    crud_user,
    crud_api_key,
    crud_api_usage,
    crud_role,
    crud_user_role,
)
from preloop.models.db.session import get_db_session
from preloop.models.models.user import User as UserModel
from preloop.models.models.api_key import ApiKey
from pydantic import BaseModel
from preloop.services.flow_presets_service import (
    create_default_presets_for_account_background,
)
from preloop.services.approval_policy_service import (
    create_default_approval_policy_background,
)


logger = logging.getLogger(__name__)
router = APIRouter()


class OnboardingRequest(BaseModel):
    email: str
    username: str
    password: str


@router.post(
    "/register", response_model=AuthUserResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user_data: AuthUserCreate, background_tasks: BackgroundTasks, request: Request
) -> Dict[str, str]:
    """Register a new user.

    Args:
        user_data: User creation data.
        background_tasks: Background tasks for sending emails.
        request: The incoming request object.

    Returns:
        The created user.

    Raises:
        HTTPException: If the username or email is already taken, or if registration is disabled.
    """
    # Check if registration is enabled
    if not settings.registration_enabled:
        logger.warning(
            f"[REGISTER] Registration attempt blocked - registration is disabled. "
            f"Username: {user_data.username}, Email: {user_data.email}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled. Please contact an administrator for an invitation.",
        )

    logger.info(f"[REGISTER] Starting registration for username: {user_data.username}")

    # Check if username or email already exists
    # Since get_db_session() doesn't support async with, we'll use a manual approach
    logger.info("[REGISTER] Getting database session")
    session_generator = get_db_session()
    session = next(session_generator)
    logger.info("[REGISTER] Database session acquired")

    try:
        # Check if username exists using CRUD layer
        logger.info("[REGISTER] Checking if username exists")
        existing_user = crud_user.get_by_username(session, username=user_data.username)
        logger.info(
            f"[REGISTER] Username check complete, exists: {existing_user is not None}"
        )
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered",
            )

        # Check if email exists using CRUD layer
        logger.info("[REGISTER] Checking if email exists")
        existing_email = crud_user.get_by_email(session, email=user_data.email)
        logger.info(
            f"[REGISTER] Email check complete, exists: {existing_email is not None}"
        )
        if existing_email is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Create organization (Account) first
        logger.info("[REGISTER] Creating account")
        account_data = {
            "organization_name": f"{user_data.username}'s Organization",
            "is_active": True,
        }
        new_account = crud_account.create(session, obj_in=account_data)
        logger.info(f"[REGISTER] Account created with ID: {new_account.id}")

        # Create user linked to the account
        logger.info("[REGISTER] Hashing password")
        hashed_password = get_password_hash(user_data.password)
        logger.info("[REGISTER] Password hashed")
        logger.info("[REGISTER] Creating user")
        user_dict = {
            "account_id": new_account.id,
            "username": user_data.username,
            "email": user_data.email,
            "hashed_password": hashed_password,
            "full_name": user_data.full_name,
            "is_active": True,
            "email_verified": False,
            "user_source": "local",
        }
        new_user = crud_user.create(session, obj_in=user_dict)
        logger.info(f"[REGISTER] User created with ID: {new_user.id}")

        # Set this user as the primary user for the account
        logger.info("[REGISTER] Setting primary_user_id on account")
        new_account.primary_user_id = new_user.id
        session.add(new_account)
        logger.info(
            f"[REGISTER] Set user {new_user.id} as primary user for account {new_account.id}"
        )

        # Assign Owner role to the first user
        logger.info("[REGISTER] Looking up owner role")
        owner_role = crud_role.get_by_name(session, name="owner")
        logger.info(f"[REGISTER] Owner role found: {owner_role is not None}")
        if owner_role:
            user_role_data = {
                "user_id": new_user.id,
                "role_id": owner_role.id,
            }
            crud_user_role.create(session, obj_in=user_role_data)
            logger.info(f"Assigned Owner role to user {new_user.username}")
        else:
            logger.warning(
                "Owner role not found in database - user will have no permissions"
            )

        try:
            logger.info("[REGISTER] Committing transaction")
            session.commit()
            logger.info("[REGISTER] Transaction committed, refreshing objects")
            session.refresh(new_user)
            session.refresh(new_account)
            logger.info("[REGISTER] Objects refreshed")

            # Generate email verification token
            logger.info("[REGISTER] Generating email verification token")
            token = create_email_verification_token(user_data.email)
            logger.info("[REGISTER] Token generated")

            # Send verification email as a background task
            logger.info("[REGISTER] Scheduling verification email")
            background_tasks.add_task(
                send_verification_email, user_email=user_data.email, token=token
            )
            logger.info("[REGISTER] Verification email scheduled")

            # Create default flow presets for the new account
            logger.info("[REGISTER] Scheduling flow presets creation")
            background_tasks.add_task(
                create_default_presets_for_account_background,
                account_id=new_account.id,
            )
            logger.info("[REGISTER] Flow presets creation scheduled")

            # Create default approval policy for the new account
            # In single-user mode, set the new user as the approver
            logger.info("[REGISTER] Scheduling default approval policy creation")
            background_tasks.add_task(
                create_default_approval_policy_background,
                account_id=new_account.id,
                user_id=new_user.id,
            )
            logger.info("[REGISTER] Default approval policy creation scheduled")

            # Send product notification email
            logger.info("[REGISTER] Sending product notification email")
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
                    source_ip=get_client_ip(request),
                    tracker_data=None,
                )
                logger.info("[REGISTER] Product notification email sent")
            except Exception as e:
                logger.error(
                    f"Failed to send product notification email for user {new_user.email}: {str(e)}"
                )

            logger.info("[REGISTER] Registration complete, returning response")
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
            # Find the user using CRUD layer
            user = crud_user.get_by_email(session, email=email)

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
        # Find user using CRUD layer
        user = crud_user.get_by_email(session, email=reset_data.email)

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
            # Find user using CRUD layer
            user = crud_user.get_by_email(session, email=email)

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
        data={"sub": str(user.id), "scopes": form_data.scopes or []},
        expires_delta=access_token_expires,
    )

    # Create refresh token with longer expiration
    refresh_token_expires = timedelta(days=7)  # 7 days
    refresh_token = create_access_token(
        data={"sub": str(user.id), "scopes": form_data.scopes or [], "refresh": True},
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
        data={"sub": str(user.id), "scopes": []},
        expires_delta=access_token_expires,
    )

    # Create refresh token with longer expiration
    refresh_token_expires = timedelta(days=7)  # 7 days
    refresh_token = create_access_token(
        data={"sub": str(user.id), "scopes": [], "refresh": True},
        expires_delta=refresh_token_expires,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # in seconds
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(request: RefreshRequest) -> Dict[str, str]:
    """Refresh an access token using a refresh token.

    Args:
        request: Refresh token request.

    Returns:
        New access token.

    Raises:
        HTTPException: If the refresh token is invalid or expired.
    """
    # Get synchronous database session
    session_generator = get_db_session()
    session = next(session_generator)

    try:
        # Decode and validate the refresh token
        token_data = decode_token(request.refresh_token)

        # Parse user_id from token
        try:
            user_id = UUID(token_data.sub)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user ID in token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verify user exists and is active using CRUD layer
        user = crud_user.get(session, id=user_id)

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
    finally:
        session.close()


@router.get("/users/me", response_model=AuthUserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)) -> User:
    """Get the current user.

    Args:
        current_user: The current user.

    Returns:
        The current user.
    """
    return current_user


@router.put("/users/me", response_model=AuthUserResponse)
async def update_user_me(
    *,
    db: Session = Depends(get_db_session),
    user_update: AuthUserUpdate,
    current_user: UserModel = Depends(get_current_active_user),
) -> Any:
    """Update own user."""
    user = crud_user.update(db, db_obj=current_user, obj_in=user_update)
    return user


@router.put("/users/me/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_current_user_password(
    passwords: PasswordChangeRequest,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db_session),
):
    """Change current user's password."""
    if not verify_password(passwords.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password",
        )
    hashed_password = get_password_hash(passwords.new_password)
    crud_user.update(
        db, db_obj=current_user, obj_in={"hashed_password": hashed_password}
    )


@router.post(
    "/api-keys", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED
)
async def create_api_key(
    key_data: ApiKeyCreate,
    current_user: UserModel = Depends(get_current_active_user),
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

    def _is_duplicate_name_for_account_error(err: IntegrityError) -> bool:
        orig = getattr(err, "orig", None)
        diag = getattr(orig, "diag", None)
        constraint_name = getattr(diag, "constraint_name", None)
        if constraint_name == "uix_api_key_account_id_name":
            return True

        msg = str(orig) if orig is not None else str(err)
        return (
            "uix_api_key_account_id_name" in msg
            or "UNIQUE constraint failed: api_key.account_id, api_key.name" in msg
            or ("api_key.account_id" in msg and "api_key.name" in msg)
        )

    try:
        # Create a new API key
        new_key = ApiKey(
            name=key_data.name,
            key=key_value,
            scopes=key_data.scopes,
            account_id=current_user.account_id,
            user_id=current_user.id,
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
            user_id=new_key.user_id,
            last_used_at=new_key.last_used_at,
        )
    except IntegrityError as e:
        session.rollback()
        if _is_duplicate_name_for_account_error(e):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key with this name already exists",
            )

        logger.error(f"Integrity error creating API key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error creating API key",
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
    current_user: AuthUserResponse = Depends(get_current_active_user),
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
        # Get API keys using CRUD layer
        keys = crud_api_key.get_by_user(session, username=current_user.username)

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
    current_user: AuthUserResponse = Depends(get_current_active_user),
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
            # Get specific key using CRUD layer
            key = crud_api_key.get_by_key(session, key=api_key)
            return (
                [
                    ApiKeyResponse(
                        id=key.id
                        if key
                        else UUID("00000000-0000-0000-0000-000000000000"),
                        name=key.name if key else "Not Found",
                        key=key.key if key else api_key,
                        created_at=key.created_at if key else datetime.now(UTC),
                        expires_at=key.expires_at if key else None,
                        scopes=key.scopes if key else [],
                        user_id=key.user_id if key else uuid.uuid4(),
                        last_used_at=key.last_used_at if key else None,
                    )
                ]
                if key
                else []
            )

        # Get all keys for the specified user using CRUD layer
        keys = crud_api_key.get_by_user(session, username=username)

        return [
            ApiKeyResponse(
                id=key.id,
                name=key.name,
                key=key.key,
                created_at=key.created_at,
                expires_at=key.expires_at,
                scopes=key.scopes,
                user_id=key.user_id,
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
    key_id: UUID, current_user: AuthUserResponse = Depends(get_current_active_user)
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
        # Get the key using CRUD layer
        key = crud_api_key.get_by_id_and_user(
            session, key_id=key_id, username=current_user.username
        )

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
    current_user: AuthUserResponse = Depends(get_current_active_user),
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
        # Get usage entries using CRUD layer
        usage_entries = crud_api_usage.get_for_user_filtered(
            session,
            username=current_user.username,
            start_date=start_date,
            end_date=end_date,
        )

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


async def authenticate_user(username: str, password: str) -> Optional[UserModel]:
    """Authenticate a user.

    Args:
        username: The username.
        password: The password.

    Returns:
        The user if authentication is successful, None otherwise.
    """
    from datetime import datetime, timezone

    session_generator = get_db_session()
    session = next(session_generator)

    try:
        # Find user using CRUD layer
        user = crud_user.get_by_username(session, username=username)

        if not user:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        if not user.is_active:
            return None

        # Update last_login timestamp
        user.last_login = datetime.now(timezone.utc)
        session.commit()
        session.refresh(user)

        return user
    finally:
        session.close()
        try:
            # Clean up the generator
            next(session_generator, None)
        except StopIteration:
            pass


@router.post("/complete-onboarding", response_model=Token)
async def complete_onboarding(request: OnboardingRequest) -> Dict[str, str]:
    """
    Completes the onboarding for a new user created via Stripe checkout.
    Sets the password and updates the username.
    """
    session_generator = get_db_session()
    session = next(session_generator)
    try:
        # Find user using CRUD layer
        user = crud_user.get_by_email(session, email=request.email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        if user.hashed_password != "NEEDS_RESET":
            raise HTTPException(status_code=400, detail="Onboarding already completed.")

        # Check if the new username is taken by someone else using CRUD layer
        if user.username != request.username:
            existing_user = crud_user.get_by_username(
                session, username=request.username
            )
            if existing_user:
                raise HTTPException(
                    status_code=400, detail="Username is already taken."
                )
            user.username = request.username

        user.hashed_password = get_password_hash(request.password)
        session.commit()

        # Create access and refresh tokens for auto-login
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

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    finally:
        session.close()
        try:
            next(session_generator, None)
        except StopIteration:
            pass
