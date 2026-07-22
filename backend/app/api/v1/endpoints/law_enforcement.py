"""Law enforcement portal API endpoints.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
- Credential verification for law enforcement access
- Read-only dashboard with essential case information
- No personal data exposure in portal
- Audit logging for all law enforcement access
- Automatic case cleanup on resolution
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from ....core.database import get_db
from ....middleware.law_enforcement_auth import get_current_le_officer
from ....models.law_enforcement import LawEnforcementOfficer
from ....services.law_enforcement_service import LawEnforcementService
from ....schemas.law_enforcement import (
    LERegisterRequest,
    LELoginRequest,
    LECaseAccessRequest,
    LECaseStatusUpdateRequest,
    LEAuthResponse,
    LECaseListResponse,
    LECaseDetailResponse,
    LEAccessRequestResponse,
    LEAuditListResponse,
    LEStandardResponse,
    LEOfficerResponse,
    LETokenResponse,
    LECaseAccessResponse,
    LEAuditLogResponse,
)

router = APIRouter()


# ==================== Authentication Endpoints ====================

@router.post("/register", response_model=LEStandardResponse)
async def register_officer(
    request: Request,
    data: LERegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new law enforcement officer.
    
    Requirements: 6.1 - Credential verification (pending admin verification)
    
    Note: Registration creates a pending account that requires admin verification.
    """
    officer, error = await LawEnforcementService.register_officer(
        db=db,
        badge_number_hash=data.badge_number_hash,
        name_encrypted=data.name_encrypted,
        department_encrypted=data.department_encrypted,
        email_hash=data.email_hash,
        password=data.password,
    )
    
    if error:
        return LEStandardResponse(
            success=False,
            message=error,
            code="LE_REGISTRATION_FAILED",
        )
    
    return LEStandardResponse(
        success=True,
        message="Registration submitted. Pending verification.",
        code="LE_REGISTRATION_PENDING",
        data={"officer_id": str(officer.id)},
    )


@router.post("/login", response_model=LEAuthResponse)
async def login_officer(
    request: Request,
    data: LELoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate law enforcement officer.
    
    Requirements: 6.1 - Verify official credentials before granting access
    """
    officer, error = await LawEnforcementService.authenticate_officer(
        db=db,
        email_hash=data.email_hash,
        password=data.password,
    )
    
    if error:
        # Return consistent error for security
        return LEAuthResponse(
            success=False,
            message="Invalid credentials",
            code="LE_AUTH_FAILED",
        )
    
    # Create token
    token_data = LawEnforcementService.create_officer_token(officer)
    
    return LEAuthResponse(
        success=True,
        message="Authentication successful",
        code="LE_AUTH_SUCCESS",
        data=LETokenResponse(
            access_token=token_data["access_token"],
            token_type=token_data["token_type"],
            expires_in=token_data["expires_in"],
            officer=LEOfficerResponse(
                id=str(officer.id),
                is_verified=officer.is_verified,
                is_active=officer.is_active,
                created_at=officer.created_at,
                last_login=officer.last_login,
            ),
        ),
    )


@router.get("/me", response_model=LEStandardResponse)
async def get_current_officer_info(
    officer: LawEnforcementOfficer = Depends(get_current_le_officer)
):
    """Get current authenticated officer information."""
    return LEStandardResponse(
        success=True,
        message="Officer information retrieved",
        code="LE_INFO_SUCCESS",
        data={
            "id": str(officer.id),
            "is_verified": officer.is_verified,
            "is_active": officer.is_active,
            "created_at": officer.created_at.isoformat(),
            "last_login": officer.last_login.isoformat() if officer.last_login else None,
        },
    )


# ==================== Case Access Endpoints ====================

@router.get("/cases/escalated", response_model=LECaseListResponse)
async def get_escalated_cases(
    officer: LawEnforcementOfficer = Depends(get_current_le_officer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all cases escalated to Professional Circle level.
    
    Requirements: 6.2 - Show only essential details without personal data
    
    These are cases that law enforcement can request access to.
    """
    cases = await LawEnforcementService.get_escalated_cases(db, officer.id)
    
    return LECaseListResponse(
        success=True,
        message=f"Found {len(cases)} escalated cases",
        code="LE_CASES_RETRIEVED",
        data=cases,
    )


@router.get("/cases", response_model=LECaseListResponse)
async def get_accessible_cases(
    officer: LawEnforcementOfficer = Depends(get_current_le_officer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all cases the officer has access to.
    
    Requirements: 6.2 - Show only essential details without personal data
    """
    cases = await LawEnforcementService.get_accessible_cases(db, officer.id)
    
    return LECaseListResponse(
        success=True,
        message=f"Found {len(cases)} accessible cases",
        code="LE_CASES_RETRIEVED",
        data=cases,
    )


@router.get("/cases/{case_id}", response_model=LECaseDetailResponse)
async def get_case_detail(
    case_id: str,
    officer: LawEnforcementOfficer = Depends(get_current_le_officer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed case information.
    
    Requirements: 6.2, 6.3 - Essential details without personal data, read-only access
    """
    try:
        alert_id = UUID(case_id)
    except ValueError:
        return LECaseDetailResponse(
            success=False,
            message="Invalid case ID format",
            code="LE_INVALID_CASE_ID",
        )
    
    case_detail, error = await LawEnforcementService.get_case_detail(
        db, officer.id, alert_id
    )
    
    if error:
        return LECaseDetailResponse(
            success=False,
            message=error,
            code="LE_CASE_ACCESS_DENIED" if "denied" in error.lower() else "LE_CASE_NOT_FOUND",
        )
    
    return LECaseDetailResponse(
        success=True,
        message="Case details retrieved",
        code="LE_CASE_RETRIEVED",
        data=case_detail,
    )


@router.post("/cases/access", response_model=LEAccessRequestResponse)
async def request_case_access(
    data: LECaseAccessRequest,
    officer: LawEnforcementOfficer = Depends(get_current_le_officer),
    db: AsyncSession = Depends(get_db)
):
    """
    Request access to a case.
    
    Requirements: 6.1 - Verify credentials before granting access
    
    Access is auto-approved for cases escalated to Professional Circle level.
    """
    try:
        alert_id = UUID(data.alert_id)
    except ValueError:
        return LEAccessRequestResponse(
            success=False,
            message="Invalid case ID format",
            code="LE_INVALID_CASE_ID",
        )
    
    access, error = await LawEnforcementService.request_case_access(
        db=db,
        officer_id=officer.id,
        alert_id=alert_id,
        access_reason_encrypted=data.access_reason_encrypted,
        iv=data.iv,
    )
    
    if error:
        return LEAccessRequestResponse(
            success=False,
            message=error,
            code="LE_ACCESS_REQUEST_FAILED",
        )
    
    return LEAccessRequestResponse(
        success=True,
        message="Access request submitted" if access.status.value == "pending" else "Access granted",
        code="LE_ACCESS_PENDING" if access.status.value == "pending" else "LE_ACCESS_GRANTED",
        data=LECaseAccessResponse(
            id=str(access.id),
            officer_id=str(access.officer_id),
            alert_id=str(access.alert_id),
            status=access.status,
            granted_at=access.granted_at,
            revoked_at=access.revoked_at,
            created_at=access.created_at,
        ),
    )


@router.delete("/cases/{case_id}/access", response_model=LEStandardResponse)
async def revoke_case_access(
    case_id: str,
    officer: LawEnforcementOfficer = Depends(get_current_le_officer),
    db: AsyncSession = Depends(get_db)
):
    """
    Voluntarily revoke access to a case.
    
    Requirements: 6.4 - Update status and remove sensitive information
    """
    try:
        alert_id = UUID(case_id)
    except ValueError:
        return LEStandardResponse(
            success=False,
            message="Invalid case ID format",
            code="LE_INVALID_CASE_ID",
        )
    
    success, message = await LawEnforcementService.revoke_case_access(
        db, officer.id, alert_id
    )
    
    return LEStandardResponse(
        success=success,
        message=message,
        code="LE_ACCESS_REVOKED" if success else "LE_ACCESS_REVOKE_FAILED",
    )


@router.post("/cases/{case_id}/notes", response_model=LEStandardResponse)
async def add_case_notes(
    case_id: str,
    data: LECaseStatusUpdateRequest,
    officer: LawEnforcementOfficer = Depends(get_current_le_officer),
    db: AsyncSession = Depends(get_db)
):
    """
    Add notes to a case (read-only portal, cannot resolve cases).
    
    Requirements: 6.3 - Read-only access to active alert status
    """
    try:
        alert_id = UUID(case_id)
    except ValueError:
        return LEStandardResponse(
            success=False,
            message="Invalid case ID format",
            code="LE_INVALID_CASE_ID",
        )
    
    success, message = await LawEnforcementService.update_case_status(
        db=db,
        officer_id=officer.id,
        alert_id=alert_id,
        resolution_notes_encrypted=data.resolution_notes_encrypted,
        iv=data.iv,
    )
    
    return LEStandardResponse(
        success=success,
        message=message,
        code="LE_NOTES_ADDED" if success else "LE_NOTES_FAILED",
    )


# ==================== Audit Log Endpoints ====================

@router.get("/audit", response_model=LEAuditListResponse)
async def get_my_audit_logs(
    limit: int = 100,
    officer: LawEnforcementOfficer = Depends(get_current_le_officer),
    db: AsyncSession = Depends(get_db)
):
    """
    Get audit logs for the current officer.
    
    Requirements: 6.5 - Maintain audit logs of all law enforcement access
    """
    logs = await LawEnforcementService.get_audit_logs(
        db, officer_id=officer.id, limit=limit
    )
    
    return LEAuditListResponse(
        success=True,
        message=f"Found {len(logs)} audit log entries",
        code="LE_AUDIT_RETRIEVED",
        data=[
            LEAuditLogResponse(
                id=str(log.id),
                officer_id=str(log.officer_id) if log.officer_id else None,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=str(log.resource_id) if log.resource_id else None,
                created_at=log.created_at,
            )
            for log in logs
        ],
    )
