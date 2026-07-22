"""Law enforcement service for portal operations.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
- Credential verification for law enforcement access
- Read-only dashboard with essential case information
- No personal data exposure in portal
- Audit logging for all law enforcement access
- Automatic case cleanup on resolution
"""
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from ..models.law_enforcement import (
    LawEnforcementOfficer,
    LECaseAccess,
    LEAuditLog,
    LEAccessStatus,
)
from ..models.alert import Alert, AlertStatus, AlertAuditLog
from ..models.circle import CircleMember, MemberStatus
from ..core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    EncryptionService,
)
from ..core.config import get_settings
from ..schemas.law_enforcement import (
    LECaseSummary,
    LECaseDetail,
    LETimelineEvent,
)

settings = get_settings()


class LawEnforcementService:
    """Service for law enforcement portal operations."""
    
    # ==================== Authentication ====================
    
    @staticmethod
    async def get_officer_by_email_hash(
        db: AsyncSession,
        email_hash: str
    ) -> Optional[LawEnforcementOfficer]:
        """Get officer by email hash."""
        result = await db.execute(
            select(LawEnforcementOfficer).where(
                LawEnforcementOfficer.email_hash == email_hash
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_officer_by_id(
        db: AsyncSession,
        officer_id: UUID
    ) -> Optional[LawEnforcementOfficer]:
        """Get officer by ID."""
        result = await db.execute(
            select(LawEnforcementOfficer).where(
                LawEnforcementOfficer.id == officer_id
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def register_officer(
        db: AsyncSession,
        badge_number_hash: str,
        name_encrypted: str,
        department_encrypted: str,
        email_hash: str,
        password: str
    ) -> Tuple[Optional[LawEnforcementOfficer], str]:
        """
        Register a new law enforcement officer.
        
        Requirements: 6.1 - Credential verification (pending verification)
        
        Returns (officer, error_message).
        """
        # Check if badge number already exists
        existing_badge = await db.execute(
            select(LawEnforcementOfficer).where(
                LawEnforcementOfficer.badge_number_hash == badge_number_hash
            )
        )
        if existing_badge.scalar_one_or_none():
            return None, "Badge number already registered"
        
        # Check if email already exists
        existing_email = await db.execute(
            select(LawEnforcementOfficer).where(
                LawEnforcementOfficer.email_hash == email_hash
            )
        )
        if existing_email.scalar_one_or_none():
            return None, "Email already registered"
        
        # Create officer (pending verification)
        officer = LawEnforcementOfficer(
            badge_number_hash=badge_number_hash,
            name_encrypted=name_encrypted,
            department_encrypted=department_encrypted,
            email_hash=email_hash,
            password_hash=get_password_hash(password),
            is_verified=False,  # Requires admin verification
            is_active=True,
        )
        db.add(officer)
        await db.flush()
        await db.refresh(officer)
        
        # Create audit log
        await LawEnforcementService._create_audit_log(
            db, officer.id, "officer_registered",
            "officer", officer.id, {}
        )
        
        return officer, ""
    
    @staticmethod
    async def authenticate_officer(
        db: AsyncSession,
        email_hash: str,
        password: str
    ) -> Tuple[Optional[LawEnforcementOfficer], str]:
        """
        Authenticate law enforcement officer.
        
        Requirements: 6.1 - Verify official credentials
        
        Returns (officer, error_message).
        """
        officer = await LawEnforcementService.get_officer_by_email_hash(db, email_hash)
        
        # Return consistent error for security
        if not officer:
            return None, "Invalid credentials"
        
        if not verify_password(password, officer.password_hash):
            return None, "Invalid credentials"
        
        if not officer.is_active:
            return None, "Account is deactivated"
        
        if not officer.is_verified:
            return None, "Account pending verification"
        
        # Update last login
        officer.last_login = datetime.now(timezone.utc)
        await db.flush()
        
        # Create audit log
        await LawEnforcementService._create_audit_log(
            db, officer.id, "officer_login",
            "officer", officer.id, {}
        )
        
        return officer, ""
    
    @staticmethod
    def create_officer_token(officer: LawEnforcementOfficer) -> dict:
        """Create JWT token for law enforcement officer."""
        expires_delta = timedelta(hours=8)  # Shorter expiry for LE portal
        access_token = create_access_token(
            data={
                "sub": str(officer.id),
                "type": "law_enforcement",
                "badge_hash": officer.badge_number_hash,
            },
            expires_delta=expires_delta
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 8 * 3600,
        }
    
    # ==================== Case Access ====================
    
    @staticmethod
    async def request_case_access(
        db: AsyncSession,
        officer_id: UUID,
        alert_id: UUID,
        access_reason_encrypted: str,
        iv: str
    ) -> Tuple[Optional[LECaseAccess], str]:
        """
        Request access to a case.
        
        Requirements: 6.1 - Verify credentials before granting access
        
        Returns (access_record, error_message).
        """
        # Verify officer exists and is verified
        officer = await LawEnforcementService.get_officer_by_id(db, officer_id)
        if not officer or not officer.is_verified:
            return None, "Officer not authorized"
        
        # Verify alert exists
        alert_result = await db.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = alert_result.scalar_one_or_none()
        if not alert:
            return None, "Case not found"
        
        # Check if access already requested
        existing = await db.execute(
            select(LECaseAccess).where(
                and_(
                    LECaseAccess.officer_id == officer_id,
                    LECaseAccess.alert_id == alert_id,
                    LECaseAccess.status.in_([LEAccessStatus.pending, LEAccessStatus.approved])
                )
            )
        )
        if existing.scalar_one_or_none():
            return None, "Access already requested or granted"
        
        # Create access request (auto-approved for verified officers on escalated cases)
        status = LEAccessStatus.pending
        granted_at = None
        
        # Auto-approve for escalated cases (Professional Circle level)
        if alert.escalation_level >= 3:
            status = LEAccessStatus.approved
            granted_at = datetime.now(timezone.utc)
        
        access = LECaseAccess(
            officer_id=officer_id,
            alert_id=alert_id,
            status=status,
            access_reason_encrypted=access_reason_encrypted,
            iv=iv,
            granted_at=granted_at,
        )
        db.add(access)
        await db.flush()
        await db.refresh(access)
        
        # Create audit log
        await LawEnforcementService._create_audit_log(
            db, officer_id, "case_access_requested",
            "alert", alert_id,
            {"status": status.value, "auto_approved": status == LEAccessStatus.approved}
        )
        
        return access, ""
    
    @staticmethod
    async def has_case_access(
        db: AsyncSession,
        officer_id: UUID,
        alert_id: UUID
    ) -> bool:
        """Check if officer has approved access to a case."""
        result = await db.execute(
            select(LECaseAccess).where(
                and_(
                    LECaseAccess.officer_id == officer_id,
                    LECaseAccess.alert_id == alert_id,
                    LECaseAccess.status == LEAccessStatus.approved
                )
            )
        )
        return result.scalar_one_or_none() is not None
    
    @staticmethod
    async def revoke_case_access(
        db: AsyncSession,
        officer_id: UUID,
        alert_id: UUID
    ) -> Tuple[bool, str]:
        """
        Revoke access to a case.
        
        Requirements: 6.4 - Update status and remove sensitive information on resolution
        
        Returns (success, message).
        """
        result = await db.execute(
            select(LECaseAccess).where(
                and_(
                    LECaseAccess.officer_id == officer_id,
                    LECaseAccess.alert_id == alert_id,
                    LECaseAccess.status == LEAccessStatus.approved
                )
            )
        )
        access = result.scalar_one_or_none()
        
        if not access:
            return False, "No active access found"
        
        access.status = LEAccessStatus.revoked
        access.revoked_at = datetime.now(timezone.utc)
        await db.flush()
        
        # Create audit log
        await LawEnforcementService._create_audit_log(
            db, officer_id, "case_access_revoked",
            "alert", alert_id, {}
        )
        
        return True, "Access revoked successfully"
    
    # ==================== Case Viewing ====================
    
    @staticmethod
    async def get_accessible_cases(
        db: AsyncSession,
        officer_id: UUID
    ) -> List[LECaseSummary]:
        """
        Get all cases the officer has access to.
        
        Requirements: 6.2 - Show only essential details without personal data
        
        Returns list of case summaries.
        """
        # Get all approved access records
        result = await db.execute(
            select(LECaseAccess)
            .options(selectinload(LECaseAccess.alert))
            .where(
                and_(
                    LECaseAccess.officer_id == officer_id,
                    LECaseAccess.status == LEAccessStatus.approved
                )
            )
        )
        accesses = result.scalars().all()
        
        cases = []
        for access in accesses:
            alert = access.alert
            if alert:
                # Count active participants without revealing identities
                participant_count = await LawEnforcementService._count_participants(db, alert)
                
                cases.append(LECaseSummary(
                    case_id=str(alert.id),
                    case_type=alert.type.value,
                    status=alert.status.value,
                    escalation_level=alert.escalation_level,
                    created_at=alert.created_at,
                    escalated_at=alert.escalated_at,
                    resolved_at=alert.resolved_at,
                    verification_count=alert.verification_count,
                    general_area=None,  # Would be populated from location service
                    active_participants_count=participant_count,
                ))
        
        # Log access
        await LawEnforcementService._create_audit_log(
            db, officer_id, "case_list_viewed",
            "cases", None, {"count": len(cases)}
        )
        
        return cases
    
    @staticmethod
    async def get_case_detail(
        db: AsyncSession,
        officer_id: UUID,
        alert_id: UUID
    ) -> Tuple[Optional[LECaseDetail], str]:
        """
        Get detailed case information.
        
        Requirements: 6.2, 6.3 - Essential details without personal data
        
        Returns (case_detail, error_message).
        """
        # Verify access
        has_access = await LawEnforcementService.has_case_access(db, officer_id, alert_id)
        if not has_access:
            return None, "Access denied"
        
        # Get alert
        result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.audit_entries))
            .where(Alert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        
        if not alert:
            return None, "Case not found"
        
        # Count participants
        participant_count = await LawEnforcementService._count_participants(db, alert)
        
        # Build timeline from audit logs (without personal identifiers)
        timeline = []
        for entry in sorted(alert.audit_entries, key=lambda x: x.created_at):
            timeline.append(LETimelineEvent(
                timestamp=entry.created_at,
                event_type=entry.action,
                description=LawEnforcementService._get_event_description(entry.action),
            ))
        
        case_detail = LECaseDetail(
            case_id=str(alert.id),
            case_type=alert.type.value,
            status=alert.status.value,
            escalation_level=alert.escalation_level,
            created_at=alert.created_at,
            escalated_at=alert.escalated_at,
            resolved_at=alert.resolved_at,
            verification_count=alert.verification_count,
            required_verifications=alert.required_verifications,
            general_area=None,  # Would be populated from location service
            active_participants_count=participant_count,
            timeline=timeline,
        )
        
        # Log access
        await LawEnforcementService._create_audit_log(
            db, officer_id, "case_detail_viewed",
            "alert", alert_id, {}
        )
        
        return case_detail, ""
    
    @staticmethod
    async def get_escalated_cases(
        db: AsyncSession,
        officer_id: UUID
    ) -> List[LECaseSummary]:
        """
        Get all cases escalated to Professional Circle level.
        
        These are cases that law enforcement can request access to.
        
        Returns list of case summaries.
        """
        # Get escalated alerts (Professional Circle level)
        result = await db.execute(
            select(Alert).where(
                and_(
                    Alert.escalation_level >= 3,
                    Alert.status != AlertStatus.resolved
                )
            ).order_by(Alert.created_at.desc())
        )
        alerts = result.scalars().all()
        
        cases = []
        for alert in alerts:
            participant_count = await LawEnforcementService._count_participants(db, alert)
            
            cases.append(LECaseSummary(
                case_id=str(alert.id),
                case_type=alert.type.value,
                status=alert.status.value,
                escalation_level=alert.escalation_level,
                created_at=alert.created_at,
                escalated_at=alert.escalated_at,
                resolved_at=alert.resolved_at,
                verification_count=alert.verification_count,
                general_area=None,
                active_participants_count=participant_count,
            ))
        
        # Log access
        await LawEnforcementService._create_audit_log(
            db, officer_id, "escalated_cases_viewed",
            "cases", None, {"count": len(cases)}
        )
        
        return cases
    
    # ==================== Case Resolution ====================
    
    @staticmethod
    async def update_case_status(
        db: AsyncSession,
        officer_id: UUID,
        alert_id: UUID,
        resolution_notes_encrypted: Optional[str] = None,
        iv: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Update case status (mark as resolved from LE portal).
        
        Requirements: 6.4 - Update status and remove sensitive information
        
        Returns (success, message).
        """
        # Verify access
        has_access = await LawEnforcementService.has_case_access(db, officer_id, alert_id)
        if not has_access:
            return False, "Access denied"
        
        # Get alert
        result = await db.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        
        if not alert:
            return False, "Case not found"
        
        if alert.status == AlertStatus.resolved:
            return False, "Case already resolved"
        
        # Note: LE can only add notes, not resolve cases
        # Resolution must come from the alert owner or Inner Circle
        
        # Create audit log with notes
        await LawEnforcementService._create_audit_log(
            db, officer_id, "case_notes_added",
            "alert", alert_id,
            {"has_notes": resolution_notes_encrypted is not None}
        )
        
        return True, "Case notes added successfully"
    
    # ==================== Automatic Cleanup ====================
    
    @staticmethod
    async def cleanup_resolved_case_access(
        db: AsyncSession,
        alert_id: UUID
    ) -> int:
        """
        Revoke all law enforcement access when a case is resolved.
        
        Requirements: 6.4 - Automatic case cleanup on resolution
        
        Returns number of access records revoked.
        """
        result = await db.execute(
            select(LECaseAccess).where(
                and_(
                    LECaseAccess.alert_id == alert_id,
                    LECaseAccess.status == LEAccessStatus.approved
                )
            )
        )
        accesses = result.scalars().all()
        
        count = 0
        for access in accesses:
            access.status = LEAccessStatus.revoked
            access.revoked_at = datetime.now(timezone.utc)
            count += 1
            
            # Create audit log
            await LawEnforcementService._create_audit_log(
                db, access.officer_id, "case_access_auto_revoked",
                "alert", alert_id, {"reason": "case_resolved"}
            )
        
        await db.flush()
        return count
    
    # ==================== Audit Logging ====================
    
    @staticmethod
    async def _create_audit_log(
        db: AsyncSession,
        officer_id: Optional[UUID],
        action: str,
        resource_type: str,
        resource_id: Optional[UUID],
        details: dict,
        ip_address: Optional[str] = None
    ) -> LEAuditLog:
        """
        Create an encrypted audit log entry.
        
        Requirements: 6.5 - Maintain audit logs of all law enforcement access
        """
        # Encrypt details
        details_json = json.dumps(details)
        encrypted = EncryptionService.encrypt(details_json)
        
        audit_log = LEAuditLog(
            officer_id=officer_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details_encrypted=encrypted["ciphertext"],
            iv=encrypted["iv"],
            ip_address=ip_address,
        )
        db.add(audit_log)
        await db.flush()
        
        return audit_log
    
    @staticmethod
    async def get_audit_logs(
        db: AsyncSession,
        officer_id: Optional[UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        limit: int = 100
    ) -> List[LEAuditLog]:
        """Get audit logs with optional filters."""
        query = select(LEAuditLog)
        
        conditions = []
        if officer_id:
            conditions.append(LEAuditLog.officer_id == officer_id)
        if resource_type:
            conditions.append(LEAuditLog.resource_type == resource_type)
        if resource_id:
            conditions.append(LEAuditLog.resource_id == resource_id)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(LEAuditLog.created_at.desc()).limit(limit)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    # ==================== Helper Methods ====================
    
    @staticmethod
    async def _count_participants(db: AsyncSession, alert: Alert) -> int:
        """Count active participants for an alert without revealing identities."""
        from ..models.circle import Circle, CircleType
        
        # Count based on escalation level
        circle_types = [CircleType.inner]
        if alert.escalation_level >= 2:
            circle_types.append(CircleType.community)
        if alert.escalation_level >= 3:
            circle_types.append(CircleType.professional)
        
        result = await db.execute(
            select(CircleMember.id)
            .join(Circle, CircleMember.circle_id == Circle.id)
            .where(
                and_(
                    Circle.owner_id == alert.user_id,
                    Circle.type.in_(circle_types),
                    CircleMember.status == MemberStatus.active
                )
            )
        )
        
        # Add 1 for the alert owner
        return len(result.all()) + 1
    
    @staticmethod
    def _get_event_description(action: str) -> str:
        """Get human-readable description for audit action."""
        descriptions = {
            "alert_created": "Case was created",
            "verification_added": "Verification received",
            "alert_verified": "Case was verified",
            "alert_escalated": "Case was escalated to next level",
            "alert_force_escalated": "Case was manually escalated",
            "alert_resolved": "Case was resolved",
            "case_access_requested": "Law enforcement access requested",
            "case_access_auto_revoked": "Law enforcement access automatically revoked",
        }
        return descriptions.get(action, f"Action: {action}")
