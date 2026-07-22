"""Alert service for alert management operations.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
- Multi-person verification (2-of-3 Inner Circle)
- Time-based escalation (30 min, 2 hours)
- Alert resolution with participant notification
- Encrypted audit trail
"""
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

from ..models.alert import Alert, AlertVerification, AlertAuditLog, AlertType, AlertStatus
from ..models.circle import Circle, CircleMember, CircleType, MemberStatus
from ..models.user import User
from ..core.security import EncryptionService


# Escalation timing constants (in minutes)
ESCALATION_TIME_INNER_TO_COMMUNITY = 30  # 30 minutes
ESCALATION_TIME_COMMUNITY_TO_PROFESSIONAL = 120  # 2 hours (120 minutes)


class AlertService:
    """Service for alert management operations."""
    
    # Required verifications for alert activation (2-of-3 Inner Circle)
    REQUIRED_VERIFICATIONS = 2
    
    # Escalation levels
    ESCALATION_INNER = 1
    ESCALATION_COMMUNITY = 2
    ESCALATION_PROFESSIONAL = 3
    
    @staticmethod
    async def get_alert_by_id(
        db: AsyncSession,
        alert_id: UUID
    ) -> Optional[Alert]:
        """Get alert by ID with verifications loaded."""
        result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.verifications))
            .where(Alert.id == alert_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_alerts(
        db: AsyncSession,
        user_id: UUID,
        include_resolved: bool = False
    ) -> List[Alert]:
        """Get all alerts for a user."""
        query = select(Alert).options(selectinload(Alert.verifications)).where(Alert.user_id == user_id)
        
        if not include_resolved:
            query = query.where(Alert.status != AlertStatus.resolved)
        
        query = query.order_by(Alert.created_at.desc())
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_alerts_requiring_verification(
        db: AsyncSession,
        user_id: UUID
    ) -> List[Alert]:
        """Get alerts where user can provide verification (Inner Circle member)."""
        # Get circles where user is an active member
        member_circles_query = select(CircleMember.circle_id).where(
            and_(
                CircleMember.user_id == user_id,
                CircleMember.status == MemberStatus.active
            )
        )
        
        # Get inner circles owned by users who have pending alerts
        result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.verifications))
            .join(Circle, and_(
                Circle.owner_id == Alert.user_id,
                Circle.type == CircleType.inner
            ))
            .where(
                and_(
                    Alert.status == AlertStatus.pending,
                    Circle.id.in_(member_circles_query),
                    Alert.user_id != user_id  # Can't verify own alert
                )
            )
            .order_by(Alert.created_at.desc())
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_inner_circle_members(
        db: AsyncSession,
        user_id: UUID
    ) -> List[UUID]:
        """Get active Inner Circle member IDs for a user."""
        result = await db.execute(
            select(CircleMember.user_id)
            .join(Circle, CircleMember.circle_id == Circle.id)
            .where(
                and_(
                    Circle.owner_id == user_id,
                    Circle.type == CircleType.inner,
                    CircleMember.status == MemberStatus.active
                )
            )
        )
        return [row[0] for row in result.all()]
    
    @staticmethod
    async def is_inner_circle_member(
        db: AsyncSession,
        alert_user_id: UUID,
        verifier_id: UUID
    ) -> bool:
        """Check if verifier is an Inner Circle member of the alert owner."""
        result = await db.execute(
            select(CircleMember.id)
            .join(Circle, CircleMember.circle_id == Circle.id)
            .where(
                and_(
                    Circle.owner_id == alert_user_id,
                    Circle.type == CircleType.inner,
                    CircleMember.user_id == verifier_id,
                    CircleMember.status == MemberStatus.active
                )
            )
        )
        return result.scalar_one_or_none() is not None

    
    @staticmethod
    async def create_alert(
        db: AsyncSession,
        user_id: UUID,
        alert_type: AlertType
    ) -> Tuple[Optional[Alert], str]:
        """
        Create a new alert requiring multi-person verification.
        
        Requirements: 3.1 - Multi-person verification requirement
        
        Returns (alert, error_message).
        """
        # Check if user has an active alert
        existing = await db.execute(
            select(Alert).where(
                and_(
                    Alert.user_id == user_id,
                    Alert.status.in_([AlertStatus.pending, AlertStatus.verified, AlertStatus.escalated])
                )
            )
        )
        if existing.scalar_one_or_none():
            return None, "User already has an active alert"
        
        # Check if user has an Inner Circle with enough members
        inner_members = await AlertService.get_inner_circle_members(db, user_id)
        if len(inner_members) < AlertService.REQUIRED_VERIFICATIONS:
            return None, f"Inner Circle must have at least {AlertService.REQUIRED_VERIFICATIONS} active members to create an alert"
        
        # Create alert in pending status
        alert = Alert(
            user_id=user_id,
            type=alert_type,
            status=AlertStatus.pending,
            verification_count=0,
            required_verifications=AlertService.REQUIRED_VERIFICATIONS,
            escalation_level=AlertService.ESCALATION_INNER,
        )
        db.add(alert)
        await db.flush()
        await db.refresh(alert)
        
        # Create audit log entry
        await AlertService._create_audit_log(
            db, alert.id, user_id, "alert_created",
            {"type": alert_type.value, "required_verifications": AlertService.REQUIRED_VERIFICATIONS}
        )
        
        return alert, ""
    
    @staticmethod
    async def verify_alert(
        db: AsyncSession,
        alert_id: UUID,
        verifier_id: UUID
    ) -> Tuple[Optional[AlertVerification], str]:
        """
        Verify an alert (2-of-3 Inner Circle requirement).
        
        Requirements: 3.1 - Multi-person verification (2-of-3 Inner Circle)
        Requirements: 3.2 - Notify Inner Circle immediately via encrypted channels
        
        Returns (verification, error_message).
        """
        alert = await AlertService.get_alert_by_id(db, alert_id)
        if not alert:
            return None, "Alert not found"
        
        if alert.status != AlertStatus.pending:
            return None, "Alert is not pending verification"
        
        if alert.user_id == verifier_id:
            return None, "Cannot verify your own alert"
        
        # Check if verifier is Inner Circle member
        is_member = await AlertService.is_inner_circle_member(db, alert.user_id, verifier_id)
        if not is_member:
            return None, "Only Inner Circle members can verify alerts"
        
        # Check if already verified by this user
        existing = await db.execute(
            select(AlertVerification).where(
                and_(
                    AlertVerification.alert_id == alert_id,
                    AlertVerification.verifier_id == verifier_id
                )
            )
        )
        if existing.scalar_one_or_none():
            return None, "You have already verified this alert"
        
        # Create verification
        verification = AlertVerification(
            alert_id=alert_id,
            verifier_id=verifier_id,
        )
        db.add(verification)
        
        # Update verification count
        alert.verification_count += 1
        
        # Check if alert should be activated
        if alert.verification_count >= alert.required_verifications:
            alert.status = AlertStatus.verified
            await AlertService._create_audit_log(
                db, alert.id, verifier_id, "alert_verified",
                {"verification_count": alert.verification_count}
            )
        
        await AlertService._create_audit_log(
            db, alert.id, verifier_id, "verification_added",
            {"current_count": alert.verification_count, "required": alert.required_verifications}
        )
        
        await db.flush()
        await db.refresh(verification)
        
        return verification, ""
    
    @staticmethod
    async def check_and_escalate_alert(
        db: AsyncSession,
        alert_id: UUID
    ) -> Tuple[bool, str, int]:
        """
        Check if alert should be escalated based on time.
        
        Requirements: 3.3 - Escalate to Community Circle after 30 minutes
        Requirements: 3.4 - Escalate to Professional Circle after 2 hours
        
        Returns (escalated, message, new_level).
        """
        alert = await AlertService.get_alert_by_id(db, alert_id)
        if not alert:
            return False, "Alert not found", 0
        
        if alert.status == AlertStatus.resolved:
            return False, "Alert is already resolved", alert.escalation_level
        
        if alert.status == AlertStatus.pending:
            return False, "Alert is not yet verified", alert.escalation_level
        
        now = datetime.now(timezone.utc)
        
        # Determine time reference (escalated_at or created_at)
        reference_time = alert.escalated_at or alert.created_at
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)
        
        elapsed_minutes = (now - reference_time).total_seconds() / 60
        
        # Check escalation based on current level
        if alert.escalation_level == AlertService.ESCALATION_INNER:
            if elapsed_minutes >= ESCALATION_TIME_INNER_TO_COMMUNITY:
                return await AlertService._escalate_to_level(
                    db, alert, AlertService.ESCALATION_COMMUNITY, "community"
                )
        elif alert.escalation_level == AlertService.ESCALATION_COMMUNITY:
            if elapsed_minutes >= ESCALATION_TIME_COMMUNITY_TO_PROFESSIONAL:
                return await AlertService._escalate_to_level(
                    db, alert, AlertService.ESCALATION_PROFESSIONAL, "professional"
                )
        
        return False, "No escalation needed", alert.escalation_level
    
    @staticmethod
    async def _escalate_to_level(
        db: AsyncSession,
        alert: Alert,
        new_level: int,
        circle_name: str
    ) -> Tuple[bool, str, int]:
        """Escalate alert to a new level."""
        alert.escalation_level = new_level
        alert.escalated_at = datetime.now(timezone.utc)
        alert.status = AlertStatus.escalated
        
        await AlertService._create_audit_log(
            db, alert.id, None, "alert_escalated",
            {"new_level": new_level, "target_circle": circle_name}
        )
        
        await db.flush()
        
        return True, f"Alert escalated to {circle_name} circle", new_level
    
    @staticmethod
    async def force_escalate_alert(
        db: AsyncSession,
        alert_id: UUID,
        actor_id: UUID
    ) -> Tuple[bool, str, int]:
        """
        Force escalate an alert to the next level.
        
        Returns (success, message, new_level).
        """
        alert = await AlertService.get_alert_by_id(db, alert_id)
        if not alert:
            return False, "Alert not found", 0
        
        if alert.status == AlertStatus.resolved:
            return False, "Cannot escalate resolved alert", alert.escalation_level
        
        if alert.status == AlertStatus.pending:
            return False, "Cannot escalate unverified alert", alert.escalation_level
        
        if alert.escalation_level >= AlertService.ESCALATION_PROFESSIONAL:
            return False, "Alert is already at maximum escalation level", alert.escalation_level
        
        new_level = alert.escalation_level + 1
        circle_name = "community" if new_level == AlertService.ESCALATION_COMMUNITY else "professional"
        
        alert.escalation_level = new_level
        alert.escalated_at = datetime.now(timezone.utc)
        alert.status = AlertStatus.escalated
        
        await AlertService._create_audit_log(
            db, alert.id, actor_id, "alert_force_escalated",
            {"new_level": new_level, "target_circle": circle_name}
        )
        
        await db.flush()
        
        return True, f"Alert escalated to {circle_name} circle", new_level

    
    @staticmethod
    async def resolve_alert(
        db: AsyncSession,
        alert_id: UUID,
        resolver_id: UUID,
        resolution_notes_encrypted: Optional[str] = None
    ) -> Tuple[bool, str, List[UUID]]:
        """
        Resolve an alert and notify all participants.
        
        Requirements: 3.5 - Notify all active participants and close the case
        
        Returns (success, message, participant_ids_to_notify).
        """
        alert = await AlertService.get_alert_by_id(db, alert_id)
        if not alert:
            return False, "Alert not found", []
        
        if alert.status == AlertStatus.resolved:
            return False, "Alert is already resolved", []
        
        # Only alert owner or Inner Circle members can resolve
        is_owner = alert.user_id == resolver_id
        is_inner_member = await AlertService.is_inner_circle_member(db, alert.user_id, resolver_id)
        
        if not is_owner and not is_inner_member:
            return False, "Only alert owner or Inner Circle members can resolve alerts", []
        
        # Get all participants to notify
        participants = await AlertService._get_alert_participants(db, alert)
        
        # Resolve the alert
        alert.status = AlertStatus.resolved
        alert.resolved_at = datetime.now(timezone.utc)
        alert.auto_delete_at = datetime.now(timezone.utc) + timedelta(days=90)
        
        await AlertService._create_audit_log(
            db, alert.id, resolver_id, "alert_resolved",
            {"resolution_notes": resolution_notes_encrypted is not None}
        )
        
        await db.flush()
        
        return True, "Alert resolved successfully", participants
    
    @staticmethod
    async def _get_alert_participants(
        db: AsyncSession,
        alert: Alert
    ) -> List[UUID]:
        """Get all participant IDs for an alert based on escalation level."""
        participants = set()
        
        # Always include alert owner
        participants.add(alert.user_id)
        
        # Add verifiers
        for verification in alert.verifications:
            participants.add(verification.verifier_id)
        
        # Add circle members based on escalation level
        circle_types = [CircleType.inner]
        if alert.escalation_level >= AlertService.ESCALATION_COMMUNITY:
            circle_types.append(CircleType.community)
        if alert.escalation_level >= AlertService.ESCALATION_PROFESSIONAL:
            circle_types.append(CircleType.professional)
        
        result = await db.execute(
            select(CircleMember.user_id)
            .join(Circle, CircleMember.circle_id == Circle.id)
            .where(
                and_(
                    Circle.owner_id == alert.user_id,
                    Circle.type.in_(circle_types),
                    CircleMember.status == MemberStatus.active
                )
            )
        )
        
        for row in result.all():
            participants.add(row[0])
        
        return list(participants)
    
    @staticmethod
    async def _create_audit_log(
        db: AsyncSession,
        alert_id: UUID,
        actor_id: Optional[UUID],
        action: str,
        details: dict
    ) -> AlertAuditLog:
        """
        Create an encrypted audit log entry.
        
        Requirements: 3.6 - Encrypted audit trail for all alert activities
        """
        # Encrypt the details
        details_json = json.dumps(details)
        encrypted = EncryptionService.encrypt(details_json)
        
        audit_log = AlertAuditLog(
            alert_id=alert_id,
            actor_id=actor_id,
            action=action,
            details_encrypted=encrypted["ciphertext"],
            iv=encrypted["iv"],
        )
        db.add(audit_log)
        await db.flush()
        
        return audit_log
    
    @staticmethod
    async def get_alert_audit_log(
        db: AsyncSession,
        alert_id: UUID
    ) -> List[AlertAuditLog]:
        """Get audit log entries for an alert."""
        result = await db.execute(
            select(AlertAuditLog)
            .where(AlertAuditLog.alert_id == alert_id)
            .order_by(AlertAuditLog.created_at.asc())
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_alerts_for_escalation_check(
        db: AsyncSession
    ) -> List[Alert]:
        """Get all alerts that may need escalation."""
        result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.verifications))
            .where(
                Alert.status.in_([AlertStatus.verified, AlertStatus.escalated])
            )
        )
        return list(result.scalars().all())
    
    @staticmethod
    def calculate_time_until_escalation(alert: Alert) -> Optional[int]:
        """
        Calculate minutes until next escalation.
        
        Returns None if no escalation is pending.
        """
        if alert.status not in [AlertStatus.verified, AlertStatus.escalated]:
            return None
        
        if alert.escalation_level >= AlertService.ESCALATION_PROFESSIONAL:
            return None
        
        now = datetime.now(timezone.utc)
        reference_time = alert.escalated_at or alert.created_at
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)
        
        elapsed_minutes = (now - reference_time).total_seconds() / 60
        
        if alert.escalation_level == AlertService.ESCALATION_INNER:
            remaining = ESCALATION_TIME_INNER_TO_COMMUNITY - elapsed_minutes
        else:
            remaining = ESCALATION_TIME_COMMUNITY_TO_PROFESSIONAL - elapsed_minutes
        
        return max(0, int(remaining))
    
    @staticmethod
    async def has_alert_access(
        db: AsyncSession,
        alert_id: UUID,
        user_id: UUID
    ) -> bool:
        """Check if user has access to view an alert."""
        alert = await AlertService.get_alert_by_id(db, alert_id)
        if not alert:
            return False
        
        # Owner always has access
        if alert.user_id == user_id:
            return True
        
        # Check if user is in any of the alert owner's circles based on escalation
        circle_types = [CircleType.inner]
        if alert.escalation_level >= AlertService.ESCALATION_COMMUNITY:
            circle_types.append(CircleType.community)
        if alert.escalation_level >= AlertService.ESCALATION_PROFESSIONAL:
            circle_types.append(CircleType.professional)
        
        result = await db.execute(
            select(CircleMember.id)
            .join(Circle, CircleMember.circle_id == Circle.id)
            .where(
                and_(
                    Circle.owner_id == alert.user_id,
                    Circle.type.in_(circle_types),
                    CircleMember.user_id == user_id,
                    CircleMember.status == MemberStatus.active
                )
            )
        )
        
        return result.scalar_one_or_none() is not None
