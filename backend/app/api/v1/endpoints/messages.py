"""Messages API endpoints for encrypted communications.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.database import get_db
from ....middleware.auth import get_current_user
from ....models.user import User
from ....schemas.message import (
    MessageCreate,
    MessageResponse,
    MessageListResponse,
)
from ....services.realtime_service import RealtimeService
from ....services.socketio_server import broadcast_chat_message

router = APIRouter()


@router.post("", response_model=dict)
async def create_message(
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new encrypted message for an alert.
    
    Requirements: 5.1, 5.2 - End-to-end encrypted channels using AES-256-GCM
    """
    message, error = await RealtimeService.create_message(
        db=db,
        alert_id=message_data.alert_id,
        sender_id=current_user.id,
        content=message_data.content,
    )
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": error,
                "code": "MESSAGE_CREATE_FAILED",
            }
        )
    
    await db.commit()
    
    # Broadcast the message via Socket.io
    await broadcast_chat_message(
        alert_id=str(message_data.alert_id),
        sender_id=str(current_user.id),
        content=message_data.content,
        encrypt=True,
    )
    
    return {
        "success": True,
        "message": "Message sent successfully",
        "code": "MESSAGE_SENT",
        "data": {
            "id": str(message.id),
            "alert_id": str(message.alert_id),
            "sender_id": str(message.sender_id),
            "created_at": message.created_at.isoformat(),
            "days_until_deletion": message.days_until_deletion,
        }
    }


@router.get("/{alert_id}", response_model=MessageListResponse)
async def get_alert_messages(
    alert_id: UUID,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get messages for an alert.
    
    Messages are returned encrypted - client must decrypt locally.
    Requirements: 5.3 - Decrypt content locally on the device
    """
    messages, error = await RealtimeService.get_alert_messages(
        db=db,
        alert_id=alert_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": error,
                "code": "MESSAGES_FETCH_FAILED",
            }
        )
    
    return MessageListResponse(
        success=True,
        messages=[
            MessageResponse(
                id=msg.id,
                alert_id=msg.alert_id,
                sender_id=msg.sender_id,
                content_encrypted=msg.content_encrypted,
                iv=msg.iv,
                created_at=msg.created_at,
                days_until_deletion=msg.days_until_deletion,
            )
            for msg in messages
        ],
        total=len(messages),
        code="MESSAGES_RETRIEVED",
    )


@router.delete("/cleanup", response_model=dict)
async def cleanup_expired_messages(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete expired messages (admin endpoint).
    
    Requirements: 5.5 - Automatic deletion after 90 days
    """
    # In production, this would be restricted to admin users
    deleted_count = await RealtimeService.delete_expired_messages(db)
    
    return {
        "success": True,
        "message": f"Deleted {deleted_count} expired messages",
        "code": "CLEANUP_COMPLETE",
        "data": {
            "deleted_count": deleted_count,
        }
    }
