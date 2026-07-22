"""Alert and AlertVerification database models."""
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum as PyEnum
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Enum, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..core.database import Base


class AlertType(str, PyEnum):
    """Alert type enum."""
    missing = "missing"
    emergency = "emergency"
    check_in = "check_in"


class AlertStatus(str, PyEnum):
    """Alert status enum."""
    pending = "pending"
    verified = "verified"
    escalated = "escalated"
    resolved = "resolved"


class Alert(Base):
    """Alert model for missing person alerts."""
    
    __tablename__ = "alerts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(Enum(AlertType), nullable=False)
    status = Column(Enum(AlertStatus), default=AlertStatus.pending)
    verification_count = Column(Integer, default=0)
    required_verifications = Column(Integer, default=2)
    escalation_level = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    escalated_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    auto_delete_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc) + timedelta(days=90))
    
    # Relationships
    user = relationship("User", back_populates="alerts")
    verifications = relationship("AlertVerification", back_populates="alert", cascade="all, delete-orphan")
    audit_entries = relationship("AlertAuditLog", back_populates="alert", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="alert", cascade="all, delete-orphan")
    
    @property
    def is_verified(self) -> bool:
        """Check if alert has enough verifications."""
        return self.verification_count >= self.required_verifications
    
    @property
    def can_escalate(self) -> bool:
        """Check if alert can be escalated to next level."""
        return self.status in [AlertStatus.verified, AlertStatus.escalated] and self.escalation_level < 3


class AlertVerification(Base):
    """Alert verification model for tracking who verified an alert."""
    
    __tablename__ = "alert_verifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    verifier_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    verified_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    alert = relationship("Alert", back_populates="verifications")
    verifier = relationship("User", back_populates="alert_verifications")
    
    __table_args__ = (
        UniqueConstraint('alert_id', 'verifier_id', name='uq_alert_verifier'),
    )


class AlertAuditLog(Base):
    """Encrypted audit log for alert activities."""
    
    __tablename__ = "alert_audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    details_encrypted = Column(Text, nullable=True)
    iv = Column(String(32), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    alert = relationship("Alert", back_populates="audit_entries")
    actor = relationship("User", back_populates="audit_actions")
