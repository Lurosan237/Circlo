"""Notification database models.

Requirements: 8.1, 8.2, 8.3, 8.4
- Push notifications via Firebase Cloud Messaging
- Encrypted notification payloads
- Priority-based notifications by circle type
- Offline notification queuing
"""
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Enum, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..core.database import Base


class NotificationPriority(str, PyEnum):
    """Notification priority levels based on circle type."""
    critical = "critical"  # Inner Circle - highest priority
    high = "high"          # Community Circle
    normal = "normal"      # Professional Circle
    low = "low"            # General notifications


class NotificationStatus(str, PyEnum):
    """Notification delivery status."""
    pending = "pending"    # Queued for delivery
    sent = "sent"          # Successfully sent to FCM
    delivered = "delivered"  # Confirmed delivered to device
    failed = "failed"      # Delivery failed
    expired = "expired"    # Notification expired before delivery


class NotificationType(str, PyEnum):
    """Types of notifications."""
    alert_created = "alert_created"
    alert_verified = "alert_verified"
    alert_escalated = "alert_escalated"
    alert_resolved = "alert_resolved"
    verification_request = "verification_request"
    check_request = "check_request"
    circle_invite = "circle_invite"
    circle_update = "circle_update"
    message = "message"
    system = "system"


class Notification(Base):
    """Notification model for push notifications."""
    
    __tablename__ = "notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Notification content (encrypted)
    title_encrypted = Column(Text, nullable=False)
    body_encrypted = Column(Text, nullable=False)
    data_encrypted = Column(Text, nullable=True)  # Additional payload data
    iv = Column(String(32), nullable=False)  # Initialization vector for decryption
    
    # Notification metadata
    type = Column(Enum(NotificationType), nullable=False)
    priority = Column(Enum(NotificationPriority), default=NotificationPriority.normal)
    status = Column(Enum(NotificationStatus), default=NotificationStatus.pending)
    
    # Related entities
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True, index=True)
    circle_id = Column(UUID(as_uuid=True), ForeignKey("circles.id", ondelete="SET NULL"), nullable=True)
    
    # Delivery tracking
    fcm_message_id = Column(String(255), nullable=True)  # Firebase message ID
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    scheduled_at = Column(DateTime(timezone=True), nullable=True)  # For scheduled notifications
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Notification expiry
    
    # Relationships
    user = relationship("User", backref="notifications")
    alert = relationship("Alert", backref="notifications")
    circle = relationship("Circle", backref="notifications")


class DeviceToken(Base):
    """Device token model for FCM registration."""
    
    __tablename__ = "device_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # FCM token
    token = Column(String(512), nullable=False, unique=True)
    platform = Column(String(20), nullable=False)  # 'ios', 'android', 'web'
    
    # Token status
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("User", backref="device_tokens")


class NotificationPreference(Base):
    """User notification preferences by circle type."""
    
    __tablename__ = "notification_preferences"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Preferences by circle type
    inner_circle_enabled = Column(Boolean, default=True)
    community_circle_enabled = Column(Boolean, default=True)
    professional_circle_enabled = Column(Boolean, default=True)
    
    # Notification type preferences
    alert_notifications = Column(Boolean, default=True)
    message_notifications = Column(Boolean, default=True)
    circle_notifications = Column(Boolean, default=True)
    system_notifications = Column(Boolean, default=True)
    
    # Quiet hours
    quiet_hours_enabled = Column(Boolean, default=False)
    quiet_hours_start = Column(String(5), nullable=True)  # HH:MM format
    quiet_hours_end = Column(String(5), nullable=True)    # HH:MM format
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("User", backref="notification_preferences")
