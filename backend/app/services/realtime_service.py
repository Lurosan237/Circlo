"""Real-time communication service using Socket.io with encryption.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
- End-to-end encrypted channels using AES-256-GCM
- Encrypt all content before transmission
- Real-time updates via Socket.io with encrypted payloads
- Automatic deletion after 90 days
"""
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Set
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete

from ..models.message import Message
from ..models.alert import Alert, AlertStatus
from ..models.circle import Circle, CircleMember, CircleType, MemberStatus
from ..core.security import EncryptionService, SocketIOEncryption, KeyManager


class RealtimeService:
    """Service for real-time encrypted communications."""
    
    # In-memory storage for connected users and their rooms
    # In production, use Redis for distributed state
    _connected_users: Dict[str, Set[str]] = {}  # user_id -> set of socket_ids
    _user_rooms: Dict[str, Set[str]] = {}  # user_id -> set of room_ids (alert_ids)
    _room_users: Dict[str, Set[str]] = {}  # room_id -> set of user_ids
    
    @staticmethod
    async def create_message(
        db: AsyncSession,
        alert_id: UUID,
        sender_id: UUID,
        content: str
    ) -> tuple[Optional[Message], str]:
        """
        Create an encrypted message for an alert.
        
        Requirements: 5.1, 5.2 - End-to-end encryption using AES-256-GCM
        
        Returns (message, error_message).
        """
        # Verify alert exists and is active
        result = await db.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        
        if not alert:
            return None, "Alert not found"
        
        if alert.status == AlertStatus.resolved:
            return None, "Cannot send messages to resolved alerts"
        
        # Verify sender has access to this alert
        has_access = await RealtimeService._verify_alert_access(db, alert, sender_id)
        if not has_access:
            return None, "You do not have access to this alert"
        
        # Encrypt the message content using alert-specific key
        alert_key = KeyManager.derive_alert_key(str(alert_id))
        encrypted = EncryptionService.encrypt(content, alert_key)
        
        # Create message with auto-delete set to 90 days
        message = Message(
            alert_id=alert_id,
            sender_id=sender_id,
            content_encrypted=encrypted["ciphertext"],
            iv=encrypted["iv"],
            auto_delete_at=datetime.now(timezone.utc) + timedelta(days=90),
        )
        
        db.add(message)
        await db.flush()
        await db.refresh(message)
        
        return message, ""
    
    @staticmethod
    async def get_alert_messages(
        db: AsyncSession,
        alert_id: UUID,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[Message], str]:
        """
        Get messages for an alert.
        
        Returns (messages, error_message).
        """
        # Verify alert exists
        result = await db.execute(
            select(Alert).where(Alert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        
        if not alert:
            return [], "Alert not found"
        
        # Verify user has access
        has_access = await RealtimeService._verify_alert_access(db, alert, user_id)
        if not has_access:
            return [], "You do not have access to this alert"
        
        # Get messages
        result = await db.execute(
            select(Message)
            .where(Message.alert_id == alert_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        messages = list(result.scalars().all())
        
        return messages, ""
    
    @staticmethod
    async def decrypt_message(
        message: Message,
        alert_id: UUID
    ) -> str:
        """
        Decrypt a message using the alert-specific key.
        
        Requirements: 5.3 - Decrypt content locally
        """
        alert_key = KeyManager.derive_alert_key(str(alert_id))
        encrypted_data = {
            "ciphertext": message.content_encrypted,
            "iv": message.iv,
        }
        return EncryptionService.decrypt(encrypted_data, alert_key)
    
    @staticmethod
    def encrypt_realtime_payload(
        payload: dict,
        alert_id: Optional[str] = None
    ) -> dict:
        """
        Encrypt a payload for Socket.io transmission.
        
        Requirements: 5.4 - Real-time updates with encrypted payloads
        """
        if alert_id:
            key = KeyManager.derive_alert_key(alert_id)
        else:
            key = None
        
        return SocketIOEncryption.encrypt_message(payload, key)
    
    @staticmethod
    def decrypt_realtime_payload(
        encrypted_payload: dict,
        alert_id: Optional[str] = None
    ) -> dict:
        """
        Decrypt a Socket.io payload.
        """
        if alert_id:
            key = KeyManager.derive_alert_key(alert_id)
        else:
            key = None
        
        return SocketIOEncryption.decrypt_message(encrypted_payload, key)
    
    @staticmethod
    async def delete_expired_messages(db: AsyncSession) -> int:
        """
        Delete messages that have passed their auto-delete date.
        
        Requirements: 5.5 - Automatic deletion after 90 days
        
        Returns count of deleted messages.
        """
        now = datetime.now(timezone.utc)
        
        result = await db.execute(
            delete(Message).where(Message.auto_delete_at < now)
        )
        
        await db.commit()
        return result.rowcount
    
    @staticmethod
    async def get_messages_for_deletion(
        db: AsyncSession,
        days_threshold: int = 90
    ) -> List[Message]:
        """
        Get messages that are due for deletion.
        
        Returns list of messages that should be deleted.
        """
        threshold = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        
        result = await db.execute(
            select(Message).where(Message.created_at < threshold)
        )
        
        return list(result.scalars().all())
    
    @staticmethod
    async def _verify_alert_access(
        db: AsyncSession,
        alert: Alert,
        user_id: UUID
    ) -> bool:
        """Verify if a user has access to an alert based on circle membership."""
        # Owner always has access
        if alert.user_id == user_id:
            return True
        
        # Determine which circle types have access based on escalation level
        circle_types = [CircleType.inner]
        if alert.escalation_level >= 2:
            circle_types.append(CircleType.community)
        if alert.escalation_level >= 3:
            circle_types.append(CircleType.professional)
        
        # Check if user is a member of any accessible circle
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
    
    # Room management methods for Socket.io
    @classmethod
    def join_room(cls, user_id: str, room_id: str, socket_id: str) -> None:
        """Add a user to a room (alert channel)."""
        if user_id not in cls._connected_users:
            cls._connected_users[user_id] = set()
        cls._connected_users[user_id].add(socket_id)
        
        if user_id not in cls._user_rooms:
            cls._user_rooms[user_id] = set()
        cls._user_rooms[user_id].add(room_id)
        
        if room_id not in cls._room_users:
            cls._room_users[room_id] = set()
        cls._room_users[room_id].add(user_id)
    
    @classmethod
    def leave_room(cls, user_id: str, room_id: str) -> None:
        """Remove a user from a room."""
        if user_id in cls._user_rooms:
            cls._user_rooms[user_id].discard(room_id)
        
        if room_id in cls._room_users:
            cls._room_users[room_id].discard(user_id)
    
    @classmethod
    def disconnect_user(cls, user_id: str, socket_id: str) -> None:
        """Handle user disconnection."""
        if user_id in cls._connected_users:
            cls._connected_users[user_id].discard(socket_id)
            if not cls._connected_users[user_id]:
                del cls._connected_users[user_id]
                # Clean up room memberships
                if user_id in cls._user_rooms:
                    for room_id in cls._user_rooms[user_id]:
                        if room_id in cls._room_users:
                            cls._room_users[room_id].discard(user_id)
                    del cls._user_rooms[user_id]
    
    @classmethod
    def get_room_users(cls, room_id: str) -> Set[str]:
        """Get all users in a room."""
        return cls._room_users.get(room_id, set())
    
    @classmethod
    def is_user_connected(cls, user_id: str) -> bool:
        """Check if a user is currently connected."""
        return user_id in cls._connected_users and len(cls._connected_users[user_id]) > 0
    
    @classmethod
    def get_user_rooms(cls, user_id: str) -> Set[str]:
        """Get all rooms a user is in."""
        return cls._user_rooms.get(user_id, set())
