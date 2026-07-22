"""Law enforcement access database models.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
- Credential verification for law enforcement access
- Read-only dashboard with essential case information
- No personal data exposure in portal
- Audit logging for all law enforcement access
- Automatic case cleanup on resolution
"""
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..core.database import Base


class LEAccessStatus(str, PyEnum):
    """Law enforcement access status enum."""
    pending = "pending"
    approved = "approved"
    denied = "denied"
    revoked = "revoked"


class LawEnforcementOfficer(Base):
    """Law enforcement officer model for credential verification.
    
    Requirements: 6.1 - Verify official credentials before granting access
    """
    
    __tablename__ = "law_enforcement_officers"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    badge_number_hash = Column(String(64), unique=True, nullable=False, index=True)
    name_encrypted = Column(Text, nullable=False)
    department_encrypted = Column(Text, nullable=False)
    email_hash = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    case_accesses = relationship("LECaseAccess", back_populates="officer", cascade="all, delete-orphan")
    audit_logs = relationship("LEAuditLog", back_populates="officer", cascade="all, delete-orphan")


class LECaseAccess(Base):
    """Law enforcement case access model.
    
    Requirements: 6.2, 6.3 - Read-only access to essential case information
    """
    
    __tablename__ = "le_case_access"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    officer_id = Column(UUID(as_uuid=True), ForeignKey("law_enforcement_officers.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_id = Column(UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(LEAccessStatus), default=LEAccessStatus.pending)
    access_reason_encrypted = Column(Text, nullable=False)
    iv = Column(String(32), nullable=False)
    granted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    officer = relationship("LawEnforcementOfficer", back_populates="case_accesses")
    alert = relationship("Alert", backref="le_accesses")


class LEAuditLog(Base):
    """Audit log for all law enforcement access.
    
    Requirements: 6.5 - Maintain audit logs of all law enforcement access
    """
    
    __tablename__ = "le_audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    officer_id = Column(UUID(as_uuid=True), ForeignKey("law_enforcement_officers.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    details_encrypted = Column(Text, nullable=True)
    iv = Column(String(32), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 max length
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    officer = relationship("LawEnforcementOfficer", back_populates="audit_logs")
