"""Circle management API endpoints."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from ....core.database import get_db
from ....schemas.circle import (
    CreateCircleRequest,
    AddMemberRequest,
    VerifyMemberRequest,
    CircleListResponse,
    CircleDetailResponse,
    CircleMemberDetailResponse,
    CircleResponse,
    CircleMemberResponse,
    PendingInvitationsListResponse,
    PendingInvitationResponse,
    CircleTypeEnum,
    MemberStatusEnum,
)
from ....services.circle_service import CircleService
from ....models.circle import CircleType, MemberStatus
from ....middleware.auth import get_current_user
from ....models.user import User

router = APIRouter()


def circle_to_response(circle, include_members: bool = True) -> CircleResponse:
    """Convert Circle model to CircleResponse."""
    active_members = [m for m in circle.members if m.status != MemberStatus.removed]
    
    members_response = []
    if include_members:
        members_response = [
            CircleMemberResponse(
                id=str(m.id),
                user_id=str(m.user_id),
                status=MemberStatusEnum(m.status.value),
                invited_at=m.invited_at,
                verified_at=m.verified_at,
                mutual_verified=m.mutual_verified,
            )
            for m in active_members
        ]
    
    return CircleResponse(
        id=str(circle.id),
        owner_id=str(circle.owner_id),
        type=CircleTypeEnum(circle.type.value),
        name_encrypted=circle.name_encrypted,
        max_members=circle.max_members,
        member_count=len([m for m in active_members if m.status == MemberStatus.active]),
        created_at=circle.created_at,
        members=members_response,
    )


@router.get("", response_model=CircleListResponse)
async def get_circles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all circles for the current user (owned and member of).
    
    Requirements: 2.5 - Role-based permissions
    """
    circles = await CircleService.get_all_user_circles(db, current_user.id)
    
    return CircleListResponse(
        success=True,
        message="Circles retrieved successfully",
        code="CIRCLES_RETRIEVED",
        data=[circle_to_response(c) for c in circles],
    )


@router.get("/owned", response_model=CircleListResponse)
async def get_owned_circles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all circles owned by the current user."""
    circles = await CircleService.get_user_owned_circles(db, current_user.id)
    
    return CircleListResponse(
        success=True,
        message="Owned circles retrieved successfully",
        code="OWNED_CIRCLES_RETRIEVED",
        data=[circle_to_response(c) for c in circles],
    )


@router.get("/member", response_model=CircleListResponse)
async def get_member_circles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all circles where current user is a member (not owner)."""
    circles = await CircleService.get_user_member_circles(db, current_user.id)
    
    return CircleListResponse(
        success=True,
        message="Member circles retrieved successfully",
        code="MEMBER_CIRCLES_RETRIEVED",
        data=[circle_to_response(c) for c in circles],
    )


@router.get("/invitations", response_model=PendingInvitationsListResponse)
async def get_pending_invitations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all pending circle invitations for the current user.
    
    Requirements: 2.4 - Mutual verification requirement
    """
    invitations = await CircleService.get_pending_invitations(db, current_user.id)
    
    return PendingInvitationsListResponse(
        success=True,
        message="Pending invitations retrieved successfully",
        code="INVITATIONS_RETRIEVED",
        data=[
            PendingInvitationResponse(
                circle_id=str(circle.id),
                circle_name_encrypted=circle.name_encrypted,
                circle_type=CircleTypeEnum(circle.type.value),
                owner_id=str(circle.owner_id),
                invited_at=member.invited_at,
            )
            for member, circle in invitations
        ],
    )


@router.post("", response_model=CircleDetailResponse)
async def create_circle(
    request: CreateCircleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new circle with size limit enforcement.
    
    Requirements: 2.1 - Inner Circle: 3-5 members
    Requirements: 2.2 - Community Circle: 15-30 members
    Requirements: 2.3 - Professional Circle: verified resources
    """
    circle_type = CircleType(request.type.value)
    
    circle, error_msg = await CircleService.create_circle(
        db=db,
        owner_id=current_user.id,
        circle_type=circle_type,
        name_encrypted=request.name_encrypted,
        max_members=request.max_members,
    )
    
    if not circle:
        return CircleDetailResponse(
            success=False,
            message=error_msg,
            code="CIRCLE_SIZE_EXCEEDED",
        )
    
    return CircleDetailResponse(
        success=True,
        message="Circle created successfully",
        code="CIRCLE_CREATED",
        data=circle_to_response(circle),
    )


@router.get("/{circle_id}", response_model=CircleDetailResponse)
async def get_circle(
    circle_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific circle by ID.
    
    Requirements: 2.5 - Role-based permissions
    Requirements: 2.6 - Access revocation check
    """
    try:
        circle_uuid = UUID(circle_id)
    except ValueError:
        return CircleDetailResponse(
            success=False,
            message="Invalid circle ID format",
            code="INVALID_CIRCLE_ID",
        )
    
    # Check access
    has_access = await CircleService.has_circle_access(db, circle_uuid, current_user.id)
    if not has_access:
        return CircleDetailResponse(
            success=False,
            message="Circle not found or access denied",
            code="CIRCLE_ACCESS_DENIED",
        )
    
    circle = await CircleService.get_circle_by_id(db, circle_uuid)
    
    return CircleDetailResponse(
        success=True,
        message="Circle retrieved successfully",
        code="CIRCLE_RETRIEVED",
        data=circle_to_response(circle),
    )


@router.delete("/{circle_id}", response_model=CircleDetailResponse)
async def delete_circle(
    circle_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a circle. Only the owner can delete.
    
    Requirements: 2.5 - Role-based permissions
    """
    try:
        circle_uuid = UUID(circle_id)
    except ValueError:
        return CircleDetailResponse(
            success=False,
            message="Invalid circle ID format",
            code="INVALID_CIRCLE_ID",
        )
    
    circle = await CircleService.get_circle_by_id(db, circle_uuid)
    if not circle:
        return CircleDetailResponse(
            success=False,
            message="Circle not found",
            code="CIRCLE_NOT_FOUND",
        )
    
    success, error_msg = await CircleService.delete_circle(db, circle, current_user.id)
    
    if not success:
        return CircleDetailResponse(
            success=False,
            message=error_msg,
            code="CIRCLE_DELETE_DENIED",
        )
    
    return CircleDetailResponse(
        success=True,
        message="Circle deleted successfully",
        code="CIRCLE_DELETED",
    )


@router.post("/{circle_id}/members", response_model=CircleMemberDetailResponse)
async def add_member(
    circle_id: str,
    request: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a member to a circle (creates pending invitation).
    Only circle owner can add members.
    
    Requirements: 2.4 - Mutual verification before activation
    Requirements: 2.1, 2.2, 2.3 - Circle size enforcement
    """
    try:
        circle_uuid = UUID(circle_id)
        user_uuid = UUID(request.user_id)
    except ValueError:
        return CircleMemberDetailResponse(
            success=False,
            message="Invalid ID format",
            code="INVALID_ID_FORMAT",
        )
    
    circle = await CircleService.get_circle_by_id(db, circle_uuid)
    if not circle:
        return CircleMemberDetailResponse(
            success=False,
            message="Circle not found",
            code="CIRCLE_NOT_FOUND",
        )
    
    # Only owner can add members
    if circle.owner_id != current_user.id:
        return CircleMemberDetailResponse(
            success=False,
            message="Only circle owner can add members",
            code="MEMBER_ADD_DENIED",
        )
    
    member, error_msg = await CircleService.add_member(
        db=db,
        circle=circle,
        user_id=user_uuid,
        inviter_id=current_user.id,
    )
    
    if not member:
        # Determine appropriate error code
        code = "MEMBER_ADD_FAILED"
        if "capacity" in error_msg.lower() or "maximum" in error_msg.lower():
            code = "CIRCLE_SIZE_EXCEEDED"
        elif "already" in error_msg.lower():
            code = "MEMBER_ALREADY_EXISTS"
        elif "not found" in error_msg.lower():
            code = "USER_NOT_FOUND"
        
        return CircleMemberDetailResponse(
            success=False,
            message=error_msg,
            code=code,
        )
    
    return CircleMemberDetailResponse(
        success=True,
        message="Member invitation sent successfully",
        code="MEMBER_INVITED",
        data=CircleMemberResponse(
            id=str(member.id),
            user_id=str(member.user_id),
            status=MemberStatusEnum(member.status.value),
            invited_at=member.invited_at,
            verified_at=member.verified_at,
            mutual_verified=member.mutual_verified,
        ),
    )


@router.post("/{circle_id}/verify", response_model=CircleMemberDetailResponse)
async def verify_membership(
    circle_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify membership (accept invitation).
    Called by the invited user to complete mutual verification.
    
    Requirements: 2.4 - Mutual verification before activation
    """
    try:
        circle_uuid = UUID(circle_id)
    except ValueError:
        return CircleMemberDetailResponse(
            success=False,
            message="Invalid circle ID format",
            code="INVALID_CIRCLE_ID",
        )
    
    member, error_msg = await CircleService.verify_membership(
        db=db,
        circle_id=circle_uuid,
        user_id=current_user.id,
    )
    
    if not member:
        code = "VERIFICATION_FAILED"
        if "not found" in error_msg.lower():
            code = "MEMBERSHIP_NOT_FOUND"
        elif "revoked" in error_msg.lower():
            code = "MEMBERSHIP_REVOKED"
        elif "already active" in error_msg.lower():
            code = "MEMBERSHIP_ALREADY_ACTIVE"
        elif "capacity" in error_msg.lower() or "maximum" in error_msg.lower():
            code = "CIRCLE_SIZE_EXCEEDED"
        
        return CircleMemberDetailResponse(
            success=False,
            message=error_msg,
            code=code,
        )
    
    return CircleMemberDetailResponse(
        success=True,
        message="Membership verified and activated successfully",
        code="MEMBERSHIP_VERIFIED",
        data=CircleMemberResponse(
            id=str(member.id),
            user_id=str(member.user_id),
            status=MemberStatusEnum(member.status.value),
            invited_at=member.invited_at,
            verified_at=member.verified_at,
            mutual_verified=member.mutual_verified,
        ),
    )


@router.delete("/{circle_id}/members/{user_id}", response_model=CircleMemberDetailResponse)
async def remove_member(
    circle_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Remove a member from a circle.
    Circle owner can remove any member, members can remove themselves.
    
    Requirements: 2.6 - Immediate access revocation on removal
    """
    try:
        circle_uuid = UUID(circle_id)
        user_uuid = UUID(user_id)
    except ValueError:
        return CircleMemberDetailResponse(
            success=False,
            message="Invalid ID format",
            code="INVALID_ID_FORMAT",
        )
    
    circle = await CircleService.get_circle_by_id(db, circle_uuid)
    if not circle:
        return CircleMemberDetailResponse(
            success=False,
            message="Circle not found",
            code="CIRCLE_NOT_FOUND",
        )
    
    success, error_msg = await CircleService.remove_member(
        db=db,
        circle=circle,
        user_id=user_uuid,
        remover_id=current_user.id,
    )
    
    if not success:
        code = "MEMBER_REMOVE_FAILED"
        if "only circle owner" in error_msg.lower():
            code = "MEMBER_REMOVE_DENIED"
        elif "not found" in error_msg.lower():
            code = "MEMBER_NOT_FOUND"
        elif "already been removed" in error_msg.lower():
            code = "MEMBER_ALREADY_REMOVED"
        
        return CircleMemberDetailResponse(
            success=False,
            message=error_msg,
            code=code,
        )
    
    return CircleMemberDetailResponse(
        success=True,
        message="Member removed successfully",
        code="MEMBER_REMOVED",
    )


@router.post("/{circle_id}/leave", response_model=CircleMemberDetailResponse)
async def leave_circle(
    circle_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Leave a circle (remove self from membership).
    
    Requirements: 2.6 - Immediate access revocation
    """
    try:
        circle_uuid = UUID(circle_id)
    except ValueError:
        return CircleMemberDetailResponse(
            success=False,
            message="Invalid circle ID format",
            code="INVALID_CIRCLE_ID",
        )
    
    circle = await CircleService.get_circle_by_id(db, circle_uuid)
    if not circle:
        return CircleMemberDetailResponse(
            success=False,
            message="Circle not found",
            code="CIRCLE_NOT_FOUND",
        )
    
    # Owner cannot leave their own circle
    if circle.owner_id == current_user.id:
        return CircleMemberDetailResponse(
            success=False,
            message="Circle owner cannot leave. Delete the circle instead.",
            code="OWNER_CANNOT_LEAVE",
        )
    
    success, error_msg = await CircleService.remove_member(
        db=db,
        circle=circle,
        user_id=current_user.id,
        remover_id=current_user.id,
    )
    
    if not success:
        return CircleMemberDetailResponse(
            success=False,
            message=error_msg,
            code="LEAVE_FAILED",
        )
    
    return CircleMemberDetailResponse(
        success=True,
        message="Successfully left the circle",
        code="CIRCLE_LEFT",
    )
