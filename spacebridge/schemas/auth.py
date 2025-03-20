"""Authentication schemas for request and response validation."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator


class Token(BaseModel):
    """Token response model."""

    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class TokenData(BaseModel):
    """Token data model."""

    sub: Optional[str] = None
    scopes: List[str] = []
    exp: Optional[datetime] = None
    refresh: Optional[bool] = False


class User(BaseModel):
    """User model."""

    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    email_verified: Optional[bool] = None


class UserInDB(User):
    """User in database model."""

    hashed_password: str


class UserCreate(BaseModel):
    """User creation model."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None

    @validator("username")
    def username_alphanumeric(cls, v):
        if not v.isalnum():
            raise ValueError("Username must be alphanumeric")
        return v


class UserResponse(BaseModel):
    """Response model for user data."""

    username: str
    email: EmailStr
    full_name: Optional[str] = None
    email_verified: bool


class LoginRequest(BaseModel):
    """Model for login requests."""

    username: str
    password: str


class RefreshRequest(BaseModel):
    """Model for token refresh requests."""

    refresh_token: str


class EmailVerificationRequest(BaseModel):
    """Model for email verification requests."""

    token: str


class PasswordResetRequest(BaseModel):
    """Model for password reset requests."""

    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    """Model for password reset confirmation."""

    token: str
    new_password: str = Field(..., min_length=8)


class TrackerRegisterRequest(BaseModel):
    """Model for tracker registration."""

    type: str  # 'github', 'gitlab', 'jira'
    name: str
    url: str
    token: str
    config: Optional[Dict[str, Any]] = None


class ApiKeyCreate(BaseModel):
    """Model for API key creation."""

    name: str = Field(..., min_length=1, max_length=100)
    expires_at: Optional[datetime] = None
    scopes: List[str] = Field(default_factory=list)


class ApiKeyResponse(BaseModel):
    """Response model for API key data."""

    id: UUID
    name: str
    key: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    scopes: List[str] = []
    created_by: str
    last_used_at: Optional[datetime] = None


class ApiKeySummary(BaseModel):
    """Summary model for API key data (without the key itself)."""

    id: UUID
    name: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    scopes: List[str] = []
    last_used_at: Optional[datetime] = None


class ApiUsageStatistics(BaseModel):
    """Model for API usage statistics."""

    total_requests: int
    requests_by_date: Dict[str, int]
    issues_created: int
    issues_updated: int
    issues_closed: int
    requests_by_endpoint: Dict[str, int]
