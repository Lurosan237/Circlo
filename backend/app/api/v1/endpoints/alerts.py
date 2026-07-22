"""Alert API endpoints.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
- Multi-person verification (2-of-3 Inner Circle)
- Time-based escalation (30 min, 2 hours)
- Alert resolution with participant notification
- Encrypted audit trail
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.database import get_db
from ....middleware.auth import get_current_user
from ....models.user import User
from ....models.alert import AlertType
from ....services.alert_service import AlertService
from ....schemas.alert import (
    CreateAlertRequest,
    ResolveAlertRequest,
    AlertResponse,
    AlertListResponse,
    AlertDetailResponse,
    AlertVerificationResponse,
    AlertVerificationDetailResponse,
    EscalationInfo,
    EscalationResponse,
    AlertStatusEnum,
    AlertTypeEnum,
)

router = APIRouter()


def _alert_to_response(alert) -> AlertResponse:
    """Convert Alert model to AlertResponse."""
    return AlertResponse(
        id=str(alert.id),
        user_id=str(alert.user_id),
        type=AlertTypeEnum(alert.type.value),
        status=AlertStatusEnum(alert.status.value),
        verification_count=alert.verification_count,
        required_verifications=alert.required_verifications,
        escalation_level=alert.escalation_level,
        created_at=alert.created_at,
        escalated_at=alert.escalated_at,
        resolved_at=alert.resolved_at,
        verifications=[
            AlertVerificationResponse(
                id=str(v.id),
                alert_id=str(v.alert_id),
                verifier_id=str(v.verifier_id),
                verified_at=v.verified_at,
            )
            for v in alert.verifications
        ],
    )


@router.post("", response_model=AlertDetailResponse)
async def create_alert(
    request: CreateAlertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new alert requiring multi-person verification.
    
    Requirements: 3.1 - Multi-person verification requirement
    """
    alert_type = AlertType(request.type.value)
    
    alert, error = await AlertService.create_alert(
        db=db,
        user_id=current_user.id,
        alert_type=alert_type,
    )
    
    if error:
        return AlertDetailResponse(
            success=False,
            message=error,
            code="ALERT_CREATION_FAILED",
            data=None,
        )
    
    await db.commit()
    await db.refresh(alert)
    
    return AlertDetailResponse(
        success=True,
        message="Alert created successfully. Awaiting verification from Inner Circle members.",
        code="ALERT_CREATED",
        data=_alert_to_response(alert),
    )


@router.get("", response_model=AlertListResponse)
async def get_my_alerts(
    include_resolved: bool = False,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all alerts for the current user."""
    alerts = await AlertService.get_user_alerts(
        db=db,
        user_id=current_user.id,
        include_resolved=include_resolved,
    )
    
    return AlertListResponse(
        success=True,
        message="Alerts retrieved successfully",
        code="ALERTS_RETRIEVED",
        data=[_alert_to_response(alert) for alert in alerts],
    )


@router.get("/pending-verification", response_model=AlertListResponse)
async def get_alerts_pending_verification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get alerts where current user can provide verification."""
    alerts = await AlertService.get_alerts_requiring_verification(
        db=db,
        user_id=current_user.id,
    )
    
    return AlertListResponse(
        success=True,
        message="Pending verification alerts retrieved",
        code="PENDING_ALERTS_RETRIEVED",
        data=[_alert_to_response(alert) for alert in alerts],
    )


@router.get("/{alert_id}", response_model=AlertDetailResponse)
async def get_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific alert by ID."""
    try:
        alert_uuid = UUID(alert_id)
    except ValueError:
        return AlertDetailResponse(
            success=False,
            message="Invalid alert ID format",
            code="INVALID_ALERT_ID",
            data=None,
        )
    
    # Check access
    has_access = await AlertService.has_alert_access(db, alert_uuid, current_user.id)
    if not has_access:
        return AlertDetailResponse(
            success=False,
            message="Alert not found or access denied",
            code="ALERT_NOT_FOUND",
            data=None,
        )
    
    alert = await AlertService.get_alert_by_id(db, alert_uuid)
    
    return AlertDetailResponse(
        success=True,
        message="Alert retrieved successfully",
        code="ALERT_RETRIEVED",
        data=_alert_to_response(alert),
    )



@router.post("/{alert_id}/verify", response_model=AlertVerificationDetailResponse)
async def verify_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify an alert (2-of-3 Inner Circle requirement).
    
    Requirements: 3.1 - Multi-person verification (2-of-3 Inner Circle)
    """
    try:
        alert_uuid = UUID(alert_id)
    except ValueError:
        return AlertVerificationDetailResponse(
            success=False,
            message="Invalid alert ID format",
            code="INVALID_ALERT_ID",
            data=None,
        )
    
    verification, error = await AlertService.verify_alert(
        db=db,
        alert_id=alert_uuid,
        verifier_id=current_user.id,
    )
    
    if error:
        return AlertVerificationDetailResponse(
            success=False,
            message=error,
            code="VERIFICATION_FAILED",
            data=None,
        )
    
    await db.commit()
    
    # Get updated alert to check if it's now verified
    alert = await AlertService.get_alert_by_id(db, alert_uuid)
    
    message = "Verification recorded"
    if alert.is_verified:
        message = "Alert verified and activated. Inner Circle members have been notified."
    
    return AlertVerificationDetailResponse(
        success=True,
        message=message,
        code="VERIFICATION_RECORDED",
        data=AlertVerificationResponse(
            id=str(verification.id),
            alert_id=str(verification.alert_id),
            verifier_id=str(verification.verifier_id),
            verified_at=verification.verified_at,
        ),
    )


@router.post("/{alert_id}/escalate", response_model=EscalationResponse)
async def escalate_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Force escalate an alert to the next level.
    
    Requirements: 3.3, 3.4 - Time-based escalation
    """
    try:
        alert_uuid = UUID(alert_id)
    except ValueError:
        return EscalationResponse(
            success=False,
            message="Invalid alert ID format",
            code="INVALID_ALERT_ID",
            data=None,
        )
    
    # Check access
    has_access = await AlertService.has_alert_access(db, alert_uuid, current_user.id)
    if not has_access:
        return EscalationResponse(
            success=False,
            message="Alert not found or access denied",
            code="ALERT_NOT_FOUND",
            data=None,
        )
    
    success, message, new_level = await AlertService.force_escalate_alert(
        db=db,
        alert_id=alert_uuid,
        actor_id=current_user.id,
    )
    
    if not success:
        return EscalationResponse(
            success=False,
            message=message,
            code="ESCALATION_FAILED",
            data=None,
        )
    
    await db.commit()
    
    alert = await AlertService.get_alert_by_id(db, alert_uuid)
    target_circle = "community" if new_level == 2 else "professional"
    
    return EscalationResponse(
        success=True,
        message=message,
        code="ALERT_ESCALATED",
        data=EscalationInfo(
            current_level=new_level - 1,
            next_level=new_level,
            escalated_at=alert.escalated_at,
            target_circle=target_circle,
        ),
    )


@router.post("/{alert_id}/resolve", response_model=AlertDetailResponse)
async def resolve_alert(
    alert_id: str,
    request: ResolveAlertRequest = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Resolve an alert and notify all participants.
    
    Requirements: 3.5 - Notify all active participants and close the case
    """
    try:
        alert_uuid = UUID(alert_id)
    except ValueError:
        return AlertDetailResponse(
            success=False,
            message="Invalid alert ID format",
            code="INVALID_ALERT_ID",
            data=None,
        )
    
    resolution_notes = request.resolution_notes_encrypted if request else None
    
    success, message, participants = await AlertService.resolve_alert(
        db=db,
        alert_id=alert_uuid,
        resolver_id=current_user.id,
        resolution_notes_encrypted=resolution_notes,
    )
    
    if not success:
        return AlertDetailResponse(
            success=False,
            message=message,
            code="RESOLUTION_FAILED",
            data=None,
        )
    
    await db.commit()
    
    alert = await AlertService.get_alert_by_id(db, alert_uuid)
    
    return AlertDetailResponse(
        success=True,
        message=f"Alert resolved. {len(participants)} participants notified.",
        code="ALERT_RESOLVED",
        data=_alert_to_response(alert),
    )


@router.post("/check-escalations", response_model=AlertListResponse)
async def check_escalations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Check and process any pending escalations.
    This endpoint is typically called by a background job.
    
    Requirements: 3.3, 3.4 - Time-based escalation
    """
    alerts = await AlertService.get_alerts_for_escalation_check(db)
    escalated_alerts = []
    
    for alert in alerts:
        escalated, message, new_level = await AlertService.check_and_escalate_alert(
            db=db,
            alert_id=alert.id,
        )
        if escalated:
            escalated_alerts.append(alert)
    
    if escalated_alerts:
        await db.commit()
        # Refresh alerts to get updated data
        for i, alert in enumerate(escalated_alerts):
            escalated_alerts[i] = await AlertService.get_alert_by_id(db, alert.id)
    
    return AlertListResponse(
        success=True,
        message=f"{len(escalated_alerts)} alerts escalated",
        code="ESCALATIONS_CHECKED",
        data=[_alert_to_response(alert) for alert in escalated_alerts],
    )
