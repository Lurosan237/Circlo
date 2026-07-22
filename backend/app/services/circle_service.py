"""Circle service for circle management operations."""
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload
from ..models.circle import Circle, CircleMember, CircleType, MemberStatus
from ..models.user import User


class CircleService:
    """Service for circle management operations."""
    
    # Circle size limits per type
    CIRCLE_LIMITS = {
        CircleType.inner: (3, 5),      # min 3, max 5
        CircleType.community: (15, 30), # min 15, max 30
        CircleType.professional: (1, 50), # min 1, max 50
    }
    
    @staticmethod
    def get_circle_limits(circle_type: CircleType) -> Tuple[int, int]:
        """Get min and max member limits for circle type."""
        return CircleService.CIRCLE_LIMITS.get(circle_type, (1, 50))
    
    @staticmethod
    def validate_max_members(circle_type: CircleType, max_members: int) -> Tuple[bool, str]:
        """
        Validate max_members against circle type limits.
        Returns (is_valid, error_message).
        
        Requirements: 2.1, 2.2, 2.3 - Circle size enforcement
        """
        min_limit, max_limit = CircleService.get_circle_limits(circle_type)
        
        if max_members < min_limit:
            return False, f"{circle_type.value} circle must have at least {min_limit} members"
        if max_members > max_limit:
            return False, f"{circle_type.value} circle cannot exceed {max_limit} members"
        
        return True, ""
    
    @staticmethod
    async def get_circle_by_id(
        db: AsyncSession,
        circle_id: UUID
    ) -> Optional[Circle]:
        """Get circle by ID with members loaded."""
        result = await db.execute(
            select(Circle)
            .options(selectinload(Circle.members))
            .where(Circle.id == circle_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_owned_circles(
        db: AsyncSession,
        user_id: UUID
    ) -> List[Circle]:
        """Get all circles owned by a user."""
        result = await db.execute(
            select(Circle)
            .options(selectinload(Circle.members))
            .where(Circle.owner_id == user_id)
            .order_by(Circle.created_at.desc())
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_user_member_circles(
        db: AsyncSession,
        user_id: UUID
    ) -> List[Circle]:
        """Get all circles where user is a member (not owner)."""
        result = await db.execute(
            select(Circle)
            .options(selectinload(Circle.members))
            .join(CircleMember, Circle.id == CircleMember.circle_id)
            .where(
                and_(
                    CircleMember.user_id == user_id,
                    CircleMember.status == MemberStatus.active,
                    Circle.owner_id != user_id
                )
            )
            .order_by(Circle.created_at.desc())
        )
        return list(result.scalars().all())
    
    @staticmethod
    async def get_all_user_circles(
        db: AsyncSession,
        user_id: UUID
    ) -> List[Circle]:
        """Get all circles where user is owner or active member."""
        # Get owned circles
        owned = await CircleService.get_user_owned_circles(db, user_id)
        # Get member circles
        member_of = await CircleService.get_user_member_circles(db, user_id)
        
        # Combine and deduplicate
        circle_ids = set()
        all_circles = []
        for circle in owned + member_of:
            if circle.id not in circle_ids:
                circle_ids.add(circle.id)
                all_circles.append(circle)
        
        return all_circles
    
    @staticmethod
    async def create_circle(
        db: AsyncSession,
        owner_id: UUID,
        circle_type: CircleType,
        name_encrypted: str,
        max_members: int
    ) -> Tuple[Optional[Circle], str]:
        """
        Create a new circle with size limit validation.
        Returns (circle, error_message).
        
        Requirements: 2.1, 2.2, 2.3 - Circle size enforcement
        """
        # Validate max_members
        is_valid, error_msg = CircleService.validate_max_members(circle_type, max_members)
        if not is_valid:
            return None, error_msg
        
        circle = Circle(
            owner_id=owner_id,
            type=circle_type,
            name_encrypted=name_encrypted,
            max_members=max_members,
        )
        db.add(circle)
        await db.flush()
        await db.refresh(circle)
        
        return circle, ""
    
    @staticmethod
    async def get_active_member_count(
        db: AsyncSession,
        circle_id: UUID
    ) -> int:
        """Get count of active members in a circle."""
        result = await db.execute(
            select(func.count(CircleMember.id))
            .where(
                and_(
                    CircleMember.circle_id == circle_id,
                    CircleMember.status == MemberStatus.active
                )
            )
        )
        return result.scalar() or 0
    
    @staticmethod
    async def can_add_member(
        db: AsyncSession,
        circle: Circle
    ) -> Tuple[bool, str]:
        """
        Check if a member can be added to the circle.
        Returns (can_add, error_message).
        
        Requirements: 2.1, 2.2, 2.3 - Circle size enforcement
        """
        active_count = await CircleService.get_active_member_count(db, circle.id)
        
        if active_count >= circle.max_members:
            return False, f"Circle has reached maximum capacity of {circle.max_members} members"
        
        return True, ""
    
    @staticmethod
    async def get_member(
        db: AsyncSession,
        circle_id: UUID,
        user_id: UUID
    ) -> Optional[CircleMember]:
        """Get a specific member from a circle."""
        result = await db.execute(
            select(CircleMember)
            .where(
                and_(
                    CircleMember.circle_id == circle_id,
                    CircleMember.user_id == user_id
                )
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def add_member(
        db: AsyncSession,
        circle: Circle,
        user_id: UUID,
        inviter_id: UUID
    ) -> Tuple[Optional[CircleMember], str]:
        """
        Add a member to a circle (pending verification).
        Returns (member, error_message).
        
        Requirements: 2.4 - Mutual verification before activation
        """
        # Check if user exists
        user_result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            return None, "User not found"
        
        # Check if already a member
        existing = await CircleService.get_member(db, circle.id, user_id)
        if existing:
            if existing.status == MemberStatus.removed:
                # Re-invite removed member
                existing.status = MemberStatus.pending
                existing.invited_at = datetime.now(timezone.utc)
                existing.verified_at = None
                existing.mutual_verified = False
                await db.flush()
                return existing, ""
            return None, "User is already a member of this circle"
        
        # Check capacity
        can_add, error_msg = await CircleService.can_add_member(db, circle)
        if not can_add:
            return None, error_msg
        
        # Create pending membership
        member = CircleMember(
            circle_id=circle.id,
            user_id=user_id,
            status=MemberStatus.pending,
            mutual_verified=False,
        )
        db.add(member)
        await db.flush()
        await db.refresh(member)
        
        return member, ""
    
    @staticmethod
    async def verify_membership(
        db: AsyncSession,
        circle_id: UUID,
        user_id: UUID
    ) -> Tuple[Optional[CircleMember], str]:
        """
        Verify membership from the invited user's side.
        Activates membership only when mutual verification is complete.
        Returns (member, error_message).
        
        Requirements: 2.4 - Mutual verification before activation
        """
        member = await CircleService.get_member(db, circle_id, user_id)
        if not member:
            return None, "Membership not found"
        
        if member.status == MemberStatus.removed:
            return None, "Membership has been revoked"
        
        if member.status == MemberStatus.active:
            return None, "Membership is already active"
        
        # Get circle to check capacity before activation
        circle = await CircleService.get_circle_by_id(db, circle_id)
        if not circle:
            return None, "Circle not found"
        
        # Check capacity before activating
        can_add, error_msg = await CircleService.can_add_member(db, circle)
        if not can_add:
            return None, error_msg
        
        # Mark as mutually verified and activate
        member.mutual_verified = True
        member.verified_at = datetime.now(timezone.utc)
        member.status = MemberStatus.active
        
        await db.flush()
        await db.refresh(member)
        
        return member, ""
    
    @staticmethod
    async def remove_member(
        db: AsyncSession,
        circle: Circle,
        user_id: UUID,
        remover_id: UUID
    ) -> Tuple[bool, str]:
        """
        Remove a member from a circle.
        Only circle owner or the member themselves can remove.
        Returns (success, error_message).
        
        Requirements: 2.6 - Immediate access revocation on removal
        """
        # Check permissions
        is_owner = circle.owner_id == remover_id
        is_self = user_id == remover_id
        
        if not is_owner and not is_self:
            return False, "Only circle owner or the member can remove membership"
        
        member = await CircleService.get_member(db, circle.id, user_id)
        if not member:
            return False, "Member not found in circle"
        
        if member.status == MemberStatus.removed:
            return False, "Member has already been removed"
        
        # Immediately revoke access
        member.status = MemberStatus.removed
        member.mutual_verified = False
        
        await db.flush()
        
        return True, ""
    
    @staticmethod
    async def delete_circle(
        db: AsyncSession,
        circle: Circle,
        user_id: UUID
    ) -> Tuple[bool, str]:
        """
        Delete a circle. Only owner can delete.
        Returns (success, error_message).
        """
        if circle.owner_id != user_id:
            return False, "Only circle owner can delete the circle"
        
        await db.delete(circle)
        await db.flush()
        
        return True, ""
    
    @staticmethod
    async def get_pending_invitations(
        db: AsyncSession,
        user_id: UUID
    ) -> List[Tuple[CircleMember, Circle]]:
        """Get all pending invitations for a user."""
        result = await db.execute(
            select(CircleMember, Circle)
            .join(Circle, CircleMember.circle_id == Circle.id)
            .where(
                and_(
                    CircleMember.user_id == user_id,
                    CircleMember.status == MemberStatus.pending
                )
            )
            .order_by(CircleMember.invited_at.desc())
        )
        return list(result.all())
    
    @staticmethod
    async def is_circle_member(
        db: AsyncSession,
        circle_id: UUID,
        user_id: UUID
    ) -> bool:
        """Check if user is an active member of a circle."""
        member = await CircleService.get_member(db, circle_id, user_id)
        return member is not None and member.status == MemberStatus.active
    
    @staticmethod
    async def is_circle_owner(
        db: AsyncSession,
        circle_id: UUID,
        user_id: UUID
    ) -> bool:
        """Check if user is the owner of a circle."""
        circle = await CircleService.get_circle_by_id(db, circle_id)
        return circle is not None and circle.owner_id == user_id
    
    @staticmethod
    async def has_circle_access(
        db: AsyncSession,
        circle_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        Check if user has access to a circle (owner or active member).
        
        Requirements: 2.5 - Role-based permissions
        Requirements: 2.6 - Access revocation check
        """
        circle = await CircleService.get_circle_by_id(db, circle_id)
        if not circle:
            return False
        
        # Owner always has access
        if circle.owner_id == user_id:
            return True
        
        # Check if active member
        return await CircleService.is_circle_member(db, circle_id, user_id)
