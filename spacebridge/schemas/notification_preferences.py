"""Pydantic schemas for notification preferences."""

import uuid
from typing import Optional, List, Dict
from datetime import datetime

from pydantic import BaseModel, Field


class NotificationPreferencesBase(BaseModel):
    """Base schema for notification preferences."""

    preferred_channel: str = Field(
        "email", description="Preferred notification channel: 'email' or 'mobile_push'"
    )
    enable_email: bool = Field(
        True, description="Whether email notifications are enabled"
    )
    enable_mobile_push: bool = Field(
        False, description="Whether mobile push notifications are enabled"
    )


class NotificationPreferencesUpdate(NotificationPreferencesBase):
    """Schema for updating notification preferences."""

    preferred_channel: Optional[str] = Field(
        None, description="Preferred notification channel"
    )
    enable_email: Optional[bool] = Field(None, description="Enable email notifications")
    enable_mobile_push: Optional[bool] = Field(
        None, description="Enable mobile push notifications"
    )


class NotificationPreferencesResponse(NotificationPreferencesBase):
    """Schema for notification preferences response."""

    id: uuid.UUID
    user_id: uuid.UUID
    mobile_device_tokens: Optional[List[Dict]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MobileDeviceRegistration(BaseModel):
    """Schema for registering a mobile device."""

    platform: str = Field(..., description="Device platform: 'ios' or 'android'")
    token: str = Field(..., description="Device push notification token")


class QRCodeResponse(BaseModel):
    """Schema for QR code registration response."""

    token: str = Field(..., description="Registration token")
    qr_data: str = Field(..., description="QR code data (URL)")
    expires_at: str = Field(..., description="Token expiry timestamp")
    expires_in_seconds: int = Field(..., description="Seconds until expiry")
