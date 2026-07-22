"""Notification service for push notification management.

Requirements: 8.1, 8.2, 8.3, 8.4
- Push notifications via Firebase Cloud Messaging
- Encrypted notification payloads
- Priority-based notifications by circle type
- Offline notification queuing
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update
from sqlalchemy.orm import selectinload

from ..models.notification import (
    Notification, DeviceToken, NotificationPreference,
    NotificationPriority, NotificationStatus, NotificationType
)
from ..models.circle import Circle, CircleMember, CircleType, MemberStatus
from ..models.user import User
from ..core.security import EncryptionService
from ..core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


# Priority mapping for circle types
CIRCLE_TYPE_PRIORITY = {
    CircleType.inner: NotificationPriority.critical,
    CircleType.community: NotificationPriority.high,
    CircleType.professional: NotificationPriority.normal,
}

# FCM priority mapping
FCM_PRIORITY_MAP = {
    NotificationPriority.critical: "high",
    NotificationPriority.high: "high",
    NotificationPriority.normal: "normal",
    NotificationPriority.low: "normal",
}


class NotificationService:
    """Service for notification management operations."""
    
    # ==================== Device Token Management ====================
    
    @staticmethod
    async def register_device_token(
        db: AsyncSession,
        user_id: UUID,
        token: str,
        platform: str
    ) -> Tuple[Optional[DeviceToken], str]:
        """
        Register or update a device token for push notifications.
        
        Returns (device_token, error_message).
        """
        # Check if token already exists
        result = await db.execute(
            select(DeviceToken).where(DeviceToken.token == token)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing token
            if existing.user_id != user_id:
                # Token belongs to different user, reassign
                existing.user_id = user_id
            existing.is_active = True
            existing.last_used_at = datetime.now(timezone.utc)
            existing.platform = platform
            await db.flush()
            await db.refresh(existing)
            return existing, ""
        
        # Create new token
        device_token = DeviceToken(
            user_id=user_id,
            token=token,
            platform=platform,
            is_active=True,
        )
        db.add(device_token)
        await db.flush()
        await db.refresh(device_token)
        
        return device_token, ""
    
    @staticmethod
    async def unregister_device_token(
        db: AsyncSession,
        user_id: UUID,
        token: str
    ) -> Tuple[bool, str]:
        """
        Unregister a device token.
        
        Returns (success, error_message).
        """
        result = await db.execute(
            select(DeviceToken).where(
                and_(
                    DeviceToken.user_id == user_id,
                    DeviceToken.token == token
                )
            )
        )
        device_token = result.scalar_one_or_none()
        
        if not device_token:
            return False, "Device token not found"
        
        device_token.is_active = False
        await db.flush()
        
        return True, ""
    
    @staticmethod
    async def get_user_device_tokens(
        db: AsyncSession,
        user_id: UUID,
        active_only: bool = True
    ) -> List[DeviceToken]:
        """Get all device tokens for a user."""
        query = select(DeviceToken).where(DeviceToken.user_id == user_id)
        
        if active_only:
            query = query.where(DeviceToken.is_active == True)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    # ==================== Notification Preferences ====================
    
    @staticmethod
    async def get_or_create_preferences(
        db: AsyncSession,
        user_id: UUID
    ) -> NotificationPreference:
        """Get or create notification preferences for a user."""
        result = await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id
            )
        )
        preferences = result.scalar_one_or_none()
        
        if not preferences:
            preferences = NotificationPreference(user_id=user_id)
            db.add(preferences)
            await db.flush()
            await db.refresh(preferences)
        
        return preferences
    
    @staticmethod
    async def update_preferences(
        db: AsyncSession,
        user_id: UUID,
        updates: Dict[str, Any]
    ) -> Tuple[Optional[NotificationPreference], str]:
        """
        Update notification preferences.
        
        Returns (preferences, error_message).
        """
        preferences = await NotificationService.get_or_create_preferences(db, user_id)
        
        for key, value in updates.items():
            if hasattr(preferences, key) and value is not None:
                setattr(preferences, key, value)
        
        await db.flush()
        await db.refresh(preferences)
        
        return preferences, ""
    
    @staticmethod
    async def should_send_notification(
        db: AsyncSession,
        user_id: UUID,
        notification_type: NotificationType,
        circle_type: Optional[CircleType] = None
    ) -> bool:
        """
        Check if notification should be sent based on user preferences.
        
        Requirements: 8.5 - User notification preferences by circle type
        """
        preferences = await NotificationService.get_or_create_preferences(db, user_id)
        
        # Check notification type preference
        type_enabled = True
        if notification_type in [NotificationType.alert_created, NotificationType.alert_verified,
                                  NotificationType.alert_escalated, NotificationType.alert_resolved,
                                  NotificationType.verification_request, NotificationType.check_request]:
            type_enabled = preferences.alert_notifications
        elif notification_type == NotificationType.message:
            type_enabled = preferences.message_notifications
        elif notification_type in [NotificationType.circle_invite, NotificationType.circle_update]:
            type_enabled = preferences.circle_notifications
        elif notification_type == NotificationType.system:
            type_enabled = preferences.system_notifications
        
        if not type_enabled:
            return False
        
        # Check circle type preference
        if circle_type:
            if circle_type == CircleType.inner and not preferences.inner_circle_enabled:
                return False
            if circle_type == CircleType.community and not preferences.community_circle_enabled:
                return False
            if circle_type == CircleType.professional and not preferences.professional_circle_enabled:
                return False
        
        # Check quiet hours
        if preferences.quiet_hours_enabled and preferences.quiet_hours_start and preferences.quiet_hours_end:
            now = datetime.now(timezone.utc)
            current_time = now.strftime("%H:%M")
            
            start = preferences.quiet_hours_start
            end = preferences.quiet_hours_end
            
            # Handle overnight quiet hours (e.g., 22:00 to 07:00)
            if start <= end:
                if start <= current_time <= end:
                    return False
            else:
                if current_time >= start or current_time <= end:
                    return False
        
        return True
    
    # ==================== Notification Creation ====================
    
    @staticmethod
    def _encrypt_notification_content(
        title: str,
        body: str,
        data: Optional[dict] = None
    ) -> Tuple[str, str, Optional[str], str]:
        """
        Encrypt notification content.
        
        Requirements: 8.2 - Encrypted notification payloads
        
        Returns (title_encrypted, body_encrypted, data_encrypted, iv_json).
        The iv_json contains all IVs needed for decryption as a JSON string.
        """
        # Encrypt title
        title_result = EncryptionService.encrypt(title)
        
        # Encrypt body
        body_result = EncryptionService.encrypt(body)
        
        # Encrypt data if provided (including empty dicts)
        data_encrypted = None
        data_iv = None
        if data is not None:
            data_json = json.dumps(data)
            data_result = EncryptionService.encrypt(data_json)
            data_encrypted = data_result["ciphertext"]
            data_iv = data_result["iv"]
        
        # Store all IVs as JSON
        iv_data = {
            "title_iv": title_result["iv"],
            "body_iv": body_result["iv"],
            "data_iv": data_iv,
        }
        
        return title_result["ciphertext"], body_result["ciphertext"], data_encrypted, json.dumps(iv_data)
    
    @staticmethod
    def _decrypt_notification_content(
        title_encrypted: str,
        body_encrypted: str,
        data_encrypted: Optional[str],
        iv: str
    ) -> Tuple[str, str, Optional[dict]]:
        """Decrypt notification content."""
        # Parse IV data
        iv_data = json.loads(iv)
        
        title = EncryptionService.decrypt({"ciphertext": title_encrypted, "iv": iv_data["title_iv"]})
        body = EncryptionService.decrypt({"ciphertext": body_encrypted, "iv": iv_data["body_iv"]})
        
        data = None
        if data_encrypted and iv_data.get("data_iv"):
            data_json = EncryptionService.decrypt({"ciphertext": data_encrypted, "iv": iv_data["data_iv"]})
            data = json.loads(data_json)
        
        return title, body, data
    
    @staticmethod
    def get_priority_for_circle_type(circle_type: CircleType) -> NotificationPriority:
        """
        Get notification priority based on circle type.
        
        Requirements: 8.3 - Different notification priorities based on circle membership
        """
        return CIRCLE_TYPE_PRIORITY.get(circle_type, NotificationPriority.normal)
    
    @staticmethod
    async def create_notification(
        db: AsyncSession,
        user_id: UUID,
        title: str,
        body: str,
        notification_type: NotificationType,
        priority: NotificationPriority = NotificationPriority.normal,
        data: Optional[dict] = None,
        alert_id: Optional[UUID] = None,
        circle_id: Optional[UUID] = None,
        scheduled_at: Optional[datetime] = None,
        circle_type: Optional[CircleType] = None
    ) -> Tuple[Optional[Notification], str]:
        """
        Create a new notification with encrypted content.
        
        Requirements: 8.1, 8.2, 8.4
        
        Returns (notification, error_message).
        """
        # Check user preferences
        should_send = await NotificationService.should_send_notification(
            db, user_id, notification_type, circle_type
        )
        
        if not should_send:
            return None, "Notification blocked by user preferences"
        
        # Encrypt content
        title_encrypted, body_encrypted, data_encrypted, iv = \
            NotificationService._encrypt_notification_content(title, body, data)
        
        # Create notification
        notification = Notification(
            user_id=user_id,
            title_encrypted=title_encrypted,
            body_encrypted=body_encrypted,
            data_encrypted=data_encrypted,
            iv=iv,
            type=notification_type,
            priority=priority,
            status=NotificationStatus.pending,
            alert_id=alert_id,
            circle_id=circle_id,
            scheduled_at=scheduled_at,
        )
        
        db.add(notification)
        await db.flush()
        await db.refresh(notification)
        
        return notification, ""
    
    @staticmethod
    async def create_batch_notifications(
        db: AsyncSession,
        user_ids: List[UUID],
        title: str,
        body: str,
        notification_type: NotificationType,
        priority: NotificationPriority = NotificationPriority.normal,
        data: Optional[dict] = None,
        alert_id: Optional[UUID] = None,
        circle_id: Optional[UUID] = None,
        circle_type: Optional[CircleType] = None
    ) -> List[Notification]:
        """
        Create notifications for multiple users.
        
        Returns list of created notifications.
        """
        notifications = []
        
        for user_id in user_ids:
            notification, error = await NotificationService.create_notification(
                db=db,
                user_id=user_id,
                title=title,
                body=body,
                notification_type=notification_type,
                priority=priority,
                data=data,
                alert_id=alert_id,
                circle_id=circle_id,
                circle_type=circle_type,
            )
            
            if notification:
                notifications.append(notification)
        
        return notifications
    
    # ==================== Notification Sending ====================
    
    @staticmethod
    def build_fcm_payload(
        notification: Notification,
        title: str,
        body: str,
        data: Optional[dict] = None
    ) -> dict:
        """
        Build encrypted FCM payload.
        
        Requirements: 8.2 - Encrypted notification payloads
        """
        # Build the payload to encrypt
        payload_data = {
            "notification_id": str(notification.id),
            "type": notification.type.value,
            "title": title,
            "body": body,
            "data": data or {},
            "alert_id": str(notification.alert_id) if notification.alert_id else None,
            "circle_id": str(notification.circle_id) if notification.circle_id else None,
            "created_at": notification.created_at.isoformat(),
        }
        
        # Encrypt the payload
        encrypted = EncryptionService.encrypt(json.dumps(payload_data))
        
        return {
            "encrypted": True,
            "payload": encrypted["ciphertext"],
            "iv": encrypted["iv"],
            "notification_id": str(notification.id),
            "type": notification.type.value,
            "priority": notification.priority.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    @staticmethod
    async def send_notification(
        db: AsyncSession,
        notification: Notification
    ) -> Tuple[bool, str]:
        """
        Send a notification via FCM.
        
        Requirements: 8.1 - Push notifications via Firebase Cloud Messaging
        Requirements: 8.4 - Offline notification queuing
        
        Returns (success, error_message).
        """
        # Get user's device tokens
        device_tokens = await NotificationService.get_user_device_tokens(
            db, notification.user_id, active_only=True
        )
        
        if not device_tokens:
            # Queue for later delivery (offline user)
            notification.status = NotificationStatus.pending
            await db.flush()
            return False, "No active device tokens, notification queued"
        
        # Decrypt content for FCM
        title, body, data = NotificationService._decrypt_notification_content(
            notification.title_encrypted,
            notification.body_encrypted,
            notification.data_encrypted,
            notification.iv
        )
        
        # Build FCM payload
        fcm_payload = NotificationService.build_fcm_payload(notification, title, body, data)
        
        # Get FCM priority
        fcm_priority = FCM_PRIORITY_MAP.get(notification.priority, "normal")
        
        # Send to all device tokens
        success_count = 0
        for device_token in device_tokens:
            try:
                # In production, this would call Firebase Admin SDK
                # For now, we simulate the send
                message_id = await NotificationService._send_to_fcm(
                    token=device_token.token,
                    payload=fcm_payload,
                    priority=fcm_priority,
                    platform=device_token.platform
                )
                
                if message_id:
                    success_count += 1
                    notification.fcm_message_id = message_id
                    device_token.last_used_at = datetime.now(timezone.utc)
                    
            except Exception as e:
                logger.error(f"Failed to send notification to device {device_token.id}: {e}")
                # Mark token as potentially invalid after multiple failures
                if notification.retry_count >= notification.max_retries:
                    device_token.is_active = False
        
        if success_count > 0:
            notification.status = NotificationStatus.sent
            notification.sent_at = datetime.now(timezone.utc)
            await db.flush()
            return True, f"Sent to {success_count} device(s)"
        else:
            notification.retry_count += 1
            if notification.retry_count >= notification.max_retries:
                notification.status = NotificationStatus.failed
            await db.flush()
            return False, "Failed to send to any device"
    
    @staticmethod
    async def _send_to_fcm(
        token: str,
        payload: dict,
        priority: str,
        platform: str
    ) -> Optional[str]:
        """
        Send notification to FCM.
        
        In production, this would use firebase-admin SDK.
        Returns message_id on success, None on failure.
        """
        # This is a placeholder for actual FCM integration
        # In production, use:
        # from firebase_admin import messaging
        # message = messaging.Message(
        #     data=payload,
        #     token=token,
        #     android=messaging.AndroidConfig(priority=priority),
        #     apns=messaging.APNSConfig(headers={'apns-priority': '10' if priority == 'high' else '5'})
        # )
        # response = messaging.send(message)
        # return response
        
        # For testing, return a mock message ID
        import uuid
        return f"mock-fcm-{uuid.uuid4()}"
    
    @staticmethod
    async def process_pending_notifications(
        db: AsyncSession,
        batch_size: int = 100
    ) -> Tuple[int, int]:
        """
        Process pending notifications (for offline users who come online).
        
        Requirements: 8.4 - Offline notification queuing
        
        Returns (sent_count, failed_count).
        """
        result = await db.execute(
            select(Notification)
            .where(
                and_(
                    Notification.status == NotificationStatus.pending,
                    or_(
                        Notification.scheduled_at.is_(None),
                        Notification.scheduled_at <= datetime.now(timezone.utc)
                    )
                )
            )
            .limit(batch_size)
        )
        
        pending = list(result.scalars().all())
        sent_count = 0
        failed_count = 0
        
        for notification in pending:
            success, _ = await NotificationService.send_notification(db, notification)
            if success:
                sent_count += 1
            else:
                failed_count += 1
        
        return sent_count, failed_count
    
    # ==================== Notification Retrieval ====================
    
    @staticmethod
    async def get_user_notifications(
        db: AsyncSession,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        include_content: bool = False
    ) -> Tuple[List[dict], int]:
        """
        Get notifications for a user with pagination.
        
        Returns (notifications, total_count).
        """
        # Count total
        count_result = await db.execute(
            select(Notification).where(Notification.user_id == user_id)
        )
        total = len(list(count_result.scalars().all()))
        
        # Get paginated results
        offset = (page - 1) * page_size
        result = await db.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        
        notifications = []
        for notification in result.scalars().all():
            notif_dict = {
                "id": notification.id,
                "user_id": notification.user_id,
                "type": notification.type,
                "priority": notification.priority,
                "status": notification.status,
                "alert_id": notification.alert_id,
                "circle_id": notification.circle_id,
                "created_at": notification.created_at,
                "sent_at": notification.sent_at,
                "delivered_at": notification.delivered_at,
            }
            
            if include_content:
                title, body, data = NotificationService._decrypt_notification_content(
                    notification.title_encrypted,
                    notification.body_encrypted,
                    notification.data_encrypted,
                    notification.iv
                )
                notif_dict["title"] = title
                notif_dict["body"] = body
                notif_dict["data"] = data
            
            notifications.append(notif_dict)
        
        return notifications, total
    
    @staticmethod
    async def mark_as_delivered(
        db: AsyncSession,
        notification_id: UUID,
        user_id: UUID
    ) -> Tuple[bool, str]:
        """Mark a notification as delivered."""
        result = await db.execute(
            select(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id
                )
            )
        )
        notification = result.scalar_one_or_none()
        
        if not notification:
            return False, "Notification not found"
        
        notification.status = NotificationStatus.delivered
        notification.delivered_at = datetime.now(timezone.utc)
        await db.flush()
        
        return True, ""
    
    # ==================== Alert Notifications ====================
    
    @staticmethod
    async def notify_alert_created(
        db: AsyncSession,
        alert_id: UUID,
        user_id: UUID,
        inner_circle_member_ids: List[UUID]
    ) -> List[Notification]:
        """
        Send notifications for a new alert requiring verification.
        
        Requirements: 8.1, 8.3
        """
        notifications = await NotificationService.create_batch_notifications(
            db=db,
            user_ids=inner_circle_member_ids,
            title="Verification Required",
            body="A member of your Inner Circle needs verification for a safety alert.",
            notification_type=NotificationType.verification_request,
            priority=NotificationPriority.critical,
            data={"alert_id": str(alert_id), "action": "verify"},
            alert_id=alert_id,
            circle_type=CircleType.inner,
        )
        
        # Send notifications
        for notification in notifications:
            await NotificationService.send_notification(db, notification)
        
        return notifications
    
    @staticmethod
    async def notify_alert_verified(
        db: AsyncSession,
        alert_id: UUID,
        participant_ids: List[UUID]
    ) -> List[Notification]:
        """Send notifications when an alert is verified."""
        notifications = await NotificationService.create_batch_notifications(
            db=db,
            user_ids=participant_ids,
            title="Alert Verified",
            body="A safety alert has been verified and is now active.",
            notification_type=NotificationType.alert_verified,
            priority=NotificationPriority.critical,
            data={"alert_id": str(alert_id)},
            alert_id=alert_id,
            circle_type=CircleType.inner,
        )
        
        for notification in notifications:
            await NotificationService.send_notification(db, notification)
        
        return notifications
    
    @staticmethod
    async def notify_alert_escalated(
        db: AsyncSession,
        alert_id: UUID,
        new_circle_member_ids: List[UUID],
        circle_type: CircleType
    ) -> List[Notification]:
        """
        Send notifications when an alert is escalated.
        
        Requirements: 8.3 - Priority based on circle type
        """
        priority = NotificationService.get_priority_for_circle_type(circle_type)
        circle_name = circle_type.value.capitalize()
        
        notifications = await NotificationService.create_batch_notifications(
            db=db,
            user_ids=new_circle_member_ids,
            title=f"Alert Escalated to {circle_name} Circle",
            body=f"A safety alert has been escalated and requires your attention.",
            notification_type=NotificationType.alert_escalated,
            priority=priority,
            data={"alert_id": str(alert_id), "circle_type": circle_type.value},
            alert_id=alert_id,
            circle_type=circle_type,
        )
        
        for notification in notifications:
            await NotificationService.send_notification(db, notification)
        
        return notifications
    
    @staticmethod
    async def notify_alert_resolved(
        db: AsyncSession,
        alert_id: UUID,
        participant_ids: List[UUID]
    ) -> List[Notification]:
        """Send notifications when an alert is resolved."""
        notifications = await NotificationService.create_batch_notifications(
            db=db,
            user_ids=participant_ids,
            title="Alert Resolved",
            body="The safety alert has been resolved. Thank you for your help.",
            notification_type=NotificationType.alert_resolved,
            priority=NotificationPriority.high,
            data={"alert_id": str(alert_id)},
            alert_id=alert_id,
        )
        
        for notification in notifications:
            await NotificationService.send_notification(db, notification)
        
        return notifications
