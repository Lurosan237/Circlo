"""Message model for encrypted communications during alerts.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
- End-to-end encrypted channels using AES-256-GCM
- Encrypt all content before transmission
- Decrypt content locally on the device
- Real-time updates via Socket.io with encrypted payloads
- Automatic deletion after 90 days
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import Column, String, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship
import uuid

from ..core.database import Base


class Message(Base):
    """Encrypted message for alert communications."""
    
    __tablename__ = "messages"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(PGUUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False)
    sender_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content_encrypted = Column(Text, nullable=False)
    iv = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    auto_delete_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(days=90)
    )
    
    # Relationships
    alert = relationship("Alert", back_populates="messages")
    sender = relationship("User", back_populates="messages")
    
    @property
    def is_expired(self) -> bool:
        """Check if message has passed its auto-delete date."""
        if self.auto_delete_at is None:
            return False
        now = datetime.now(timezone.utc)
        delete_at = self.auto_delete_at
        if delete_at.tzinfo is None:
            delete_at = delete_at.replace(tzinfo=timezone.utc)
        return now >= delete_at
    
    @property
    def days_until_deletion(self) -> int:
        """Calculate days until automatic deletion."""
        if self.auto_delete_at is None:
            return 90
        now = datetime.now(timezone.utc)
        delete_at = self.auto_delete_at
        if delete_at.tzinfo is None:
            delete_at = delete_at.replace(tzinfo=timezone.utc)
        delta = delete_at - now
        return max(0, delta.days)
