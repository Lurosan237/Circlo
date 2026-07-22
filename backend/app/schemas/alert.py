"""Alert schemas for request/response validation."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class AlertTypeEnum(str, Enum):
    """Alert type enum for API."""
    missing = "missing"
    emergency = "emergency"
    check_in = "check_in"


class AlertStatusEnum(str, Enum):
    """Alert status enum for API."""
    pending = "pending"
    verified = "verified"
    escalated = "escalated"
    resolved = "resolved"


class CreateAlertRequest(BaseModel):
    """Request schema for creating an alert."""
    type: AlertTypeEnum = Field(..., description="Type of alert (missing, emergency, check_in)")


class VerifyAlertRequest(BaseModel):
    """Request schema for verifying an alert."""
    alert_id: str = Field(..., description="UUID of the alert to verify")


class ResolveAlertRequest(BaseModel):
    """Request schema for resolving an alert."""
    resolution_notes_encrypted: Optional[str] = Field(None, description="Encrypted resolution notes")


class AlertVerificationResponse(BaseModel):
    """Response schema for alert verification."""
    id: str
    alert_id: str
    verifier_id: str
    verified_at: datetime
    
    class Config:
        from_attributes = True


class AlertAuditLogResponse(BaseModel):
    """Response schema for alert audit log entry."""
    id: str
    alert_id: str
    actor_id: Optional[str]
    action: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    """Response schema for alert."""
    id: str
    user_id: str
    type: AlertTypeEnum
    status: AlertStatusEnum
    verification_count: int
    required_verifications: int
    escalation_level: int
    created_at: datetime
    escalated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    verifications: List[AlertVerificationResponse] = []
    
    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    """Response schema for list of alerts."""
    success: bool
    message: str
    code: str
    data: Optional[List[AlertResponse]] = None


class AlertDetailResponse(BaseModel):
    """Response schema for single alert."""
    success: bool
    message: str
    code: str
    data: Optional[AlertResponse] = None


class AlertVerificationDetailResponse(BaseModel):
    """Response schema for verification result."""
    success: bool
    message: str
    code: str
    data: Optional[AlertVerificationResponse] = None


class EscalationInfo(BaseModel):
    """Information about alert escalation."""
    current_level: int
    next_level: int
    escalated_at: datetime
    target_circle: str  # 'community' or 'professional'


class EscalationResponse(BaseModel):
    """Response schema for escalation result."""
    success: bool
    message: str
    code: str
    data: Optional[EscalationInfo] = None
