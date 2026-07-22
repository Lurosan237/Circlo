"""Notification API endpoints.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.database import get_db
from ....middleware.auth import get_current_user
from ....models.user import User
from ....schemas.notification import (
    DeviceTokenCreate, DeviceTokenResponse,
    NotificationPreferenceUpdate, NotificationPreferenceResponse,
    NotificationResponse, NotificationListResponse,
    SendNotificationRequest,
)
from ....services.notification_service import NotificationService

router = APIRouter()


@router.post("/device-token", response_model=dict)
async def register_device_token(
    request: DeviceTokenCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Register a device token for push notifications."""
    device_token, error = await NotificationService.register_device_token(
        db=db,
        user_id=current_user.id,
        token=request.token,
        platform=request.platform
    )
    
    if error:
        raise HTTPException(status_code=400, detail={
            "success": False,
            "message": error,
            "code": "DEVICE_TOKEN_ERROR"
        })
    
    await db.commit()
    
    return {
        "success": True,
        "message": "Device token registered successfully",
        "code": "DEVICE_TOKEN_REGISTERED",
        "data": {
            "id": str(device_token.id),
            "token": device_token.token,
            "platform": device_token.platform,
            "is_active": device_token.is_active,
        }
    }


@router.delete("/device-token/{token}", response_model=dict)
async def unregister_device_token(
    token: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Unregister a device token."""
    success, error = await NotificationService.unregister_device_token(
        db=db,
        user_id=current_user.id,
        token=token
    )
    
    if not success:
        raise HTTPException(status_code=404, detail={
            "success": False,
            "message": error,
            "code": "DEVICE_TOKEN_NOT_FOUND"
        })
    
    await db.commit()
    
    return {
        "success": True,
        "message": "Device token unregistered successfully",
        "code": "DEVICE_TOKEN_UNREGISTERED"
    }


@router.get("/device-tokens", response_model=dict)
async def get_device_tokens(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all device tokens for the current user."""
    tokens = await NotificationService.get_user_device_tokens(
        db=db,
        user_id=current_user.id,
        active_only=False
    )
    
    return {
        "success": True,
        "message": "Device tokens retrieved",
        "code": "DEVICE_TOKENS_RETRIEVED",
        "data": [
            {
                "id": str(t.id),
                "token": t.token,
                "platform": t.platform,
                "is_active": t.is_active,
                "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
            }
            for t in tokens
        ]
    }


@router.get("/preferences", response_model=dict)
async def get_notification_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get notification preferences for the current user."""
    preferences = await NotificationService.get_or_create_preferences(
        db=db,
        user_id=current_user.id
    )
    
    await db.commit()
    
    return {
        "success": True,
        "message": "Preferences retrieved",
        "code": "PREFERENCES_RETRIEVED",
        "data": {
            "id": str(preferences.id),
            "user_id": str(preferences.user_id),
            "inner_circle_enabled": preferences.inner_circle_enabled,
            "community_circle_enabled": preferences.community_circle_enabled,
            "professional_circle_enabled": preferences.professional_circle_enabled,
            "alert_notifications": preferences.alert_notifications,
            "message_notifications": preferences.message_notifications,
            "circle_notifications": preferences.circle_notifications,
            "system_notifications": preferences.system_notifications,
            "quiet_hours_enabled": preferences.quiet_hours_enabled,
            "quiet_hours_start": preferences.quiet_hours_start,
            "quiet_hours_end": preferences.quiet_hours_end,
        }
    }


@router.put("/preferences", response_model=dict)
async def update_notification_preferences(
    request: NotificationPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update notification preferences."""
    updates = request.model_dump(exclude_unset=True)
    
    preferences, error = await NotificationService.update_preferences(
        db=db,
        user_id=current_user.id,
        updates=updates
    )
    
    if error:
        raise HTTPException(status_code=400, detail={
            "success": False,
            "message": error,
            "code": "PREFERENCES_UPDATE_ERROR"
        })
    
    await db.commit()
    
    return {
        "success": True,
        "message": "Preferences updated successfully",
        "code": "PREFERENCES_UPDATED",
        "data": {
            "id": str(preferences.id),
            "user_id": str(preferences.user_id),
            "inner_circle_enabled": preferences.inner_circle_enabled,
            "community_circle_enabled": preferences.community_circle_enabled,
            "professional_circle_enabled": preferences.professional_circle_enabled,
            "alert_notifications": preferences.alert_notifications,
            "message_notifications": preferences.message_notifications,
            "circle_notifications": preferences.circle_notifications,
            "system_notifications": preferences.system_notifications,
            "quiet_hours_enabled": preferences.quiet_hours_enabled,
            "quiet_hours_start": preferences.quiet_hours_start,
            "quiet_hours_end": preferences.quiet_hours_end,
        }
    }


@router.get("", response_model=dict)
async def get_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_content: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get notifications for the current user with pagination."""
    notifications, total = await NotificationService.get_user_notifications(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        include_content=include_content
    )
    
    notification_list = []
    for n in notifications:
        notif_data = {
            "id": str(n["id"]),
            "user_id": str(n["user_id"]),
            "type": n["type"].value,
            "priority": n["priority"].value,
            "status": n["status"].value,
            "alert_id": str(n["alert_id"]) if n["alert_id"] else None,
            "circle_id": str(n["circle_id"]) if n["circle_id"] else None,
            "created_at": n["created_at"].isoformat(),
            "sent_at": n["sent_at"].isoformat() if n["sent_at"] else None,
            "delivered_at": n["delivered_at"].isoformat() if n["delivered_at"] else None,
        }
        
        if include_content:
            notif_data["title"] = n.get("title")
            notif_data["body"] = n.get("body")
            notif_data["data"] = n.get("data")
        
        notification_list.append(notif_data)
    
    has_more = (page * page_size) < total
    
    return {
        "success": True,
        "message": "Notifications retrieved",
        "code": "NOTIFICATIONS_RETRIEVED",
        "data": {
            "notifications": notification_list,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": has_more,
        }
    }


@router.post("/{notification_id}/delivered", response_model=dict)
async def mark_notification_delivered(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark a notification as delivered."""
    success, error = await NotificationService.mark_as_delivered(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id
    )
    
    if not success:
        raise HTTPException(status_code=404, detail={
            "success": False,
            "message": error,
            "code": "NOTIFICATION_NOT_FOUND"
        })
    
    await db.commit()
    
    return {
        "success": True,
        "message": "Notification marked as delivered",
        "code": "NOTIFICATION_DELIVERED"
    }


@router.post("/process-pending", response_model=dict)
async def process_pending_notifications(
    batch_size: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Process pending notifications (admin/system endpoint)."""
    sent_count, failed_count = await NotificationService.process_pending_notifications(
        db=db,
        batch_size=batch_size
    )
    
    await db.commit()
    
    return {
        "success": True,
        "message": "Processed notifications",
        "code": "NOTIFICATIONS_PROCESSED",
        "data": {
            "sent": sent_count,
            "failed": failed_count,
        }
    }
