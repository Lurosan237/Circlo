"""Circle schemas for request/response validation."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class CircleTypeEnum(str, Enum):
    """Circle type enum for API."""
    inner = "inner"
    community = "community"
    professional = "professional"


class MemberStatusEnum(str, Enum):
    """Member status enum for API."""
    pending = "pending"
    active = "active"
    removed = "removed"


class CreateCircleRequest(BaseModel):
    """Request schema for creating a circle."""
    type: CircleTypeEnum = Field(..., description="Type of circle (inner, community, professional)")
    name_encrypted: str = Field(..., min_length=1, description="Encrypted circle name")
    max_members: int = Field(..., ge=1, description="Maximum number of members")


class AddMemberRequest(BaseModel):
    """Request schema for adding a member to a circle."""
    user_id: str = Field(..., description="UUID of user to add")


class VerifyMemberRequest(BaseModel):
    """Request schema for verifying a member."""
    circle_id: str = Field(..., description="UUID of the circle")


class CircleMemberResponse(BaseModel):
    """Response schema for circle member."""
    id: str
    user_id: str
    status: MemberStatusEnum
    invited_at: datetime
    verified_at: Optional[datetime] = None
    mutual_verified: bool
    
    class Config:
        from_attributes = True


class CircleResponse(BaseModel):
    """Response schema for circle."""
    id: str
    owner_id: str
    type: CircleTypeEnum
    name_encrypted: str
    max_members: int
    member_count: int
    created_at: datetime
    members: List[CircleMemberResponse] = []
    
    class Config:
        from_attributes = True


class CircleListResponse(BaseModel):
    """Response schema for list of circles."""
    success: bool
    message: str
    code: str
    data: Optional[List[CircleResponse]] = None


class CircleDetailResponse(BaseModel):
    """Response schema for single circle."""
    success: bool
    message: str
    code: str
    data: Optional[CircleResponse] = None


class CircleMemberDetailResponse(BaseModel):
    """Response schema for single member."""
    success: bool
    message: str
    code: str
    data: Optional[CircleMemberResponse] = None


class PendingInvitationResponse(BaseModel):
    """Response schema for pending invitation."""
    circle_id: str
    circle_name_encrypted: str
    circle_type: CircleTypeEnum
    owner_id: str
    invited_at: datetime


class PendingInvitationsListResponse(BaseModel):
    """Response schema for list of pending invitations."""
    success: bool
    message: str
    code: str
    data: Optional[List[PendingInvitationResponse]] = None
