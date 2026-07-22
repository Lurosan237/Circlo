"""Message schemas for API requests and responses.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class MessageBase(BaseModel):
    """Base message schema."""
    alert_id: UUID
    content_encrypted: str = Field(..., description="AES-256-GCM encrypted message content")
    iv: str = Field(..., description="Initialization vector for decryption")


class MessageCreate(BaseModel):
    """Schema for creating a new message."""
    alert_id: UUID
    content: str = Field(..., min_length=1, max_length=10000, description="Plain text message content")


class MessageResponse(BaseModel):
    """Schema for message response."""
    id: UUID
    alert_id: UUID
    sender_id: UUID
    content_encrypted: str
    iv: str
    created_at: datetime
    days_until_deletion: int
    
    class Config:
        from_attributes = True


class EncryptedMessagePayload(BaseModel):
    """Schema for encrypted Socket.io message payload."""
    encrypted: bool = True
    payload: str = Field(..., description="Base64 encoded encrypted content")
    iv: str = Field(..., description="Base64 encoded initialization vector")
    timestamp: str = Field(..., description="ISO format timestamp")


class DecryptedMessagePayload(BaseModel):
    """Schema for decrypted message content."""
    type: str = Field(..., description="Message type: chat_message, alert_update, etc.")
    alert_id: str
    sender_id: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    data: Optional[dict] = None
    sent_at: Optional[str] = None


class AlertUpdatePayload(BaseModel):
    """Schema for alert status update payload."""
    type: str = "alert_update"
    alert_id: str
    status: str
    data: Optional[dict] = None


class ChatMessagePayload(BaseModel):
    """Schema for chat message payload."""
    type: str = "chat_message"
    alert_id: str
    sender_id: str
    content: str
    sent_at: str


class MessageListResponse(BaseModel):
    """Schema for list of messages response."""
    success: bool = True
    messages: list[MessageResponse]
    total: int
    code: str = "MESSAGES_RETRIEVED"
