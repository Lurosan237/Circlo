"""User database model."""
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..core.database import Base


class User(Base):
    """User model for authentication."""
    
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_hash = Column(String(64), unique=True, nullable=False, index=True)
    name_encrypted = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_active = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    auto_delete_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc) + timedelta(days=90))
    
    # Relationships
    owned_circles = relationship("Circle", back_populates="owner", cascade="all, delete-orphan", foreign_keys="Circle.owner_id")
    circle_memberships = relationship("CircleMember", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    alert_verifications = relationship("AlertVerification", back_populates="verifier", cascade="all, delete-orphan")
    audit_actions = relationship("AlertAuditLog", back_populates="actor")
    messages = relationship("Message", back_populates="sender", cascade="all, delete-orphan")
