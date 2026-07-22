"""Circle and CircleMember database models."""
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from sqlalchemy import Column, String, DateTime, Integer, Boolean, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from ..core.database import Base


class CircleType(str, PyEnum):
    """Circle type enum representing trust levels."""
    inner = "inner"
    community = "community"
    professional = "professional"
    
    @property
    def min_members(self) -> int:
        """Get minimum members for circle type."""
        limits = {
            CircleType.inner: 3,
            CircleType.community: 15,
            CircleType.professional: 1,
        }
        return limits[self]
    
    @property
    def max_members(self) -> int:
        """Get maximum members for circle type."""
        limits = {
            CircleType.inner: 5,
            CircleType.community: 30,
            CircleType.professional: 50,
        }
        return limits[self]


class MemberStatus(str, PyEnum):
    """Member status in a circle."""
    pending = "pending"
    active = "active"
    removed = "removed"


class Circle(Base):
    """Circle model for safety circles."""
    
    __tablename__ = "circles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(Enum(CircleType), nullable=False)
    name_encrypted = Column(String, nullable=False)
    max_members = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    owner = relationship("User", back_populates="owned_circles", foreign_keys=[owner_id])
    members = relationship("CircleMember", back_populates="circle", cascade="all, delete-orphan")


class CircleMember(Base):
    """Circle member model for circle membership."""
    
    __tablename__ = "circle_members"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    circle_id = Column(UUID(as_uuid=True), ForeignKey("circles.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(MemberStatus), default=MemberStatus.pending)
    invited_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    verified_at = Column(DateTime(timezone=True), nullable=True)
    mutual_verified = Column(Boolean, default=False)
    
    # Relationships
    circle = relationship("Circle", back_populates="members")
    user = relationship("User", back_populates="circle_memberships")
    
    __table_args__ = (
        UniqueConstraint('circle_id', 'user_id', name='uq_circle_member'),
    )
