"""Notification schemas for API request/response validation.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field

from ..models.notification import NotificationPriority, NotificationStatus, NotificationType


# Device Token Schemas
class DeviceTokenCreate(BaseModel):
    """Schema for registering a device token."""
    token: str = Field(..., min_length=10, max_length=512)
    platform: str = Field(..., pattern="^(ios|android|web)$")


class DeviceTokenResponse(BaseModel):
    """Schema for device token response."""
    id: UUID
    token: str
    platform: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# Notification Preference Schemas
class NotificationPreferenceUpdate(BaseModel):
    """Schema for updating notification preferences."""
    inner_circle_enabled: Optional[bool] = None
    community_circle_enabled: Optional[bool] = None
    professional_circle_enabled: Optional[bool] = None
    alert_notifications: Optional[bool] = None
    message_notifications: Optional[bool] = None
    circle_notifications: Optional[bool] = None
    system_notifications: Optional[bool] = None
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = Field(None, pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    quiet_hours_end: Optional[str] = Field(None, pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")


class NotificationPreferenceResponse(BaseModel):
    """Schema for notification preference response."""
    id: UUID
    user_id: UUID
    inner_circle_enabled: bool
    community_circle_enabled: bool
    professional_circle_enabled: bool
    alert_notifications: bool
    message_notifications: bool
    circle_notifications: bool
    system_notifications: bool
    quiet_hours_enabled: bool
    quiet_hours_start: Optional[str]
    quiet_hours_end: Optional[str]
    
    class Config:
        from_attributes = True


# Notification Schemas
class NotificationCreate(BaseModel):
    """Schema for creating a notification (internal use)."""
    user_id: UUID
    title: str = Field(..., min_length=1, max_length=100)
    body: str = Field(..., min_length=1, max_length=500)
    data: Optional[dict] = None
    type: NotificationType
    priority: NotificationPriority = NotificationPriority.normal
    alert_id: Optional[UUID] = None
    circle_id: Optional[UUID] = None
    scheduled_at: Optional[datetime] = None


class NotificationResponse(BaseModel):
    """Schema for notification response."""
    id: UUID
    user_id: UUID
    type: NotificationType
    priority: NotificationPriority
    status: NotificationStatus
    alert_id: Optional[UUID]
    circle_id: Optional[UUID]
    created_at: datetime
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    
    # Decrypted content (only included when requested)
    title: Optional[str] = None
    body: Optional[str] = None
    data: Optional[dict] = None
    
    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Schema for paginated notification list."""
    notifications: List[NotificationResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


# Send Notification Request (for testing/admin)
class SendNotificationRequest(BaseModel):
    """Schema for manually sending a notification."""
    user_id: UUID
    title: str = Field(..., min_length=1, max_length=100)
    body: str = Field(..., min_length=1, max_length=500)
    data: Optional[dict] = None
    type: NotificationType = NotificationType.system
    priority: NotificationPriority = NotificationPriority.normal


# Batch Notification Request
class BatchNotificationRequest(BaseModel):
    """Schema for sending notifications to multiple users."""
    user_ids: List[UUID] = Field(..., min_items=1, max_items=100)
    title: str = Field(..., min_length=1, max_length=100)
    body: str = Field(..., min_length=1, max_length=500)
    data: Optional[dict] = None
    type: NotificationType
    priority: NotificationPriority = NotificationPriority.normal
    alert_id: Optional[UUID] = None
    circle_id: Optional[UUID] = None


# Encrypted Notification Payload (for FCM)
class EncryptedNotificationPayload(BaseModel):
    """Schema for encrypted notification payload sent via FCM."""
    encrypted: bool = True
    payload: str  # Base64 encoded encrypted content
    iv: str       # Initialization vector
    notification_id: str
    type: str
    priority: str
    timestamp: str
