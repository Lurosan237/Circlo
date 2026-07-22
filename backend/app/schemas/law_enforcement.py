"""Law enforcement schemas for request/response validation.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class LEAccessStatusEnum(str, Enum):
    """Law enforcement access status enum for API."""
    pending = "pending"
    approved = "approved"
    denied = "denied"
    revoked = "revoked"


# ==================== Request Schemas ====================

class LERegisterRequest(BaseModel):
    """Request schema for law enforcement officer registration."""
    badge_number_hash: str = Field(..., description="SHA-256 hash of badge number")
    name_encrypted: str = Field(..., description="Encrypted officer name")
    department_encrypted: str = Field(..., description="Encrypted department name")
    email_hash: str = Field(..., description="SHA-256 hash of email")
    password: str = Field(..., min_length=8, description="Password for authentication")


class LELoginRequest(BaseModel):
    """Request schema for law enforcement officer login."""
    email_hash: str = Field(..., description="SHA-256 hash of email")
    password: str = Field(..., description="Password for authentication")


class LECaseAccessRequest(BaseModel):
    """Request schema for requesting case access."""
    alert_id: str = Field(..., description="UUID of the alert/case to access")
    access_reason_encrypted: str = Field(..., description="Encrypted reason for access request")
    iv: str = Field(..., description="Initialization vector for encryption")


class LECaseStatusUpdateRequest(BaseModel):
    """Request schema for updating case status (resolution)."""
    resolution_notes_encrypted: Optional[str] = Field(None, description="Encrypted resolution notes")
    iv: Optional[str] = Field(None, description="Initialization vector for encryption")


# ==================== Response Schemas ====================

class LEOfficerResponse(BaseModel):
    """Response schema for law enforcement officer (no sensitive data)."""
    id: str
    is_verified: bool
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class LETokenResponse(BaseModel):
    """Response schema for law enforcement authentication token."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    officer: LEOfficerResponse


class LECaseAccessResponse(BaseModel):
    """Response schema for case access record."""
    id: str
    officer_id: str
    alert_id: str
    status: LEAccessStatusEnum
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class LECaseSummary(BaseModel):
    """Summary of a case for law enforcement view.
    
    Requirements: 6.2 - Show only essential details without revealing personal data
    """
    case_id: str
    case_type: str
    status: str
    escalation_level: int
    created_at: datetime
    escalated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    verification_count: int
    # General location area (not exact routes)
    general_area: Optional[str] = None
    # Number of active participants (not their identities)
    active_participants_count: int


class LECaseDetail(BaseModel):
    """Detailed case view for law enforcement.
    
    Requirements: 6.2, 6.3 - Essential details without personal data
    """
    case_id: str
    case_type: str
    status: str
    escalation_level: int
    created_at: datetime
    escalated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    verification_count: int
    required_verifications: int
    general_area: Optional[str] = None
    active_participants_count: int
    # Timeline of events (without personal identifiers)
    timeline: List["LETimelineEvent"]


class LETimelineEvent(BaseModel):
    """Timeline event for case history."""
    timestamp: datetime
    event_type: str
    description: str


class LEAuditLogResponse(BaseModel):
    """Response schema for audit log entry."""
    id: str
    officer_id: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# ==================== Standard Response Wrappers ====================

class LEAuthResponse(BaseModel):
    """Standard response for authentication."""
    success: bool
    message: str
    code: str
    data: Optional[LETokenResponse] = None


class LECaseListResponse(BaseModel):
    """Standard response for case list."""
    success: bool
    message: str
    code: str
    data: Optional[List[LECaseSummary]] = None


class LECaseDetailResponse(BaseModel):
    """Standard response for case detail."""
    success: bool
    message: str
    code: str
    data: Optional[LECaseDetail] = None


class LEAccessRequestResponse(BaseModel):
    """Standard response for access request."""
    success: bool
    message: str
    code: str
    data: Optional[LECaseAccessResponse] = None


class LEAuditListResponse(BaseModel):
    """Standard response for audit log list."""
    success: bool
    message: str
    code: str
    data: Optional[List[LEAuditLogResponse]] = None


class LEStandardResponse(BaseModel):
    """Standard response for general operations."""
    success: bool
    message: str
    code: str
    data: Optional[dict] = None


# Update forward references
LECaseDetail.model_rebuild()
