"""Socket.io server with encrypted payload support.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
- Set up Socket.io server with encrypted payload support
- Implement real-time alert updates with AES-256-GCM
- Create encrypted communication channels for active alerts
- Add automatic message deletion after 90 days
"""
import socketio
from datetime import datetime, timezone
from typing import Optional
import json

from ..core.security import SocketIOEncryption, KeyManager, decode_access_token
from ..core.config import get_settings
from .realtime_service import RealtimeService

settings = get_settings()

# Create Socket.io server with async support
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins=settings.cors_origins,
    logger=settings.debug,
    engineio_logger=settings.debug,
)

# Create ASGI app for Socket.io
socket_app = socketio.ASGIApp(sio)


class SocketIOManager:
    """Manager for Socket.io connections and encrypted communications."""
    
    # Store authenticated user sessions
    _sessions: dict[str, dict] = {}  # sid -> {user_id, authenticated}
    
    @classmethod
    def get_user_id(cls, sid: str) -> Optional[str]:
        """Get user ID for a socket session."""
        session = cls._sessions.get(sid)
        if session and session.get("authenticated"):
            return session.get("user_id")
        return None
    
    @classmethod
    def authenticate_session(cls, sid: str, user_id: str) -> None:
        """Mark a session as authenticated."""
        cls._sessions[sid] = {
            "user_id": user_id,
            "authenticated": True,
            "connected_at": datetime.now(timezone.utc).isoformat(),
        }
    
    @classmethod
    def remove_session(cls, sid: str) -> Optional[str]:
        """Remove a session and return the user_id."""
        session = cls._sessions.pop(sid, None)
        if session:
            return session.get("user_id")
        return None


@sio.event
async def connect(sid, environ, auth):
    """
    Handle new Socket.io connection.
    
    Requires JWT token in auth data for authentication.
    """
    print(f"[Socket.io] Connection attempt: {sid}")
    
    # Extract token from auth data
    token = None
    if auth and isinstance(auth, dict):
        token = auth.get("token")
    
    if not token:
        print(f"[Socket.io] No token provided for {sid}")
        await sio.emit("error", {
            "code": "AUTH_REQUIRED",
            "message": "Authentication token required"
        }, to=sid)
        return False
    
    # Validate token
    payload = decode_access_token(token)
    if not payload:
        print(f"[Socket.io] Invalid token for {sid}")
        await sio.emit("error", {
            "code": "AUTH_INVALID",
            "message": "Invalid authentication token"
        }, to=sid)
        return False
    
    user_id = payload.get("sub")
    if not user_id:
        print(f"[Socket.io] No user_id in token for {sid}")
        return False
    
    # Authenticate session
    SocketIOManager.authenticate_session(sid, user_id)
    print(f"[Socket.io] User {user_id} connected with session {sid}")
    
    # Send connection success
    await sio.emit("connected", {
        "success": True,
        "message": "Connected successfully",
        "user_id": user_id,
    }, to=sid)
    
    return True


@sio.event
async def disconnect(sid):
    """Handle Socket.io disconnection."""
    user_id = SocketIOManager.remove_session(sid)
    if user_id:
        RealtimeService.disconnect_user(user_id, sid)
        print(f"[Socket.io] User {user_id} disconnected (session {sid})")
    else:
        print(f"[Socket.io] Unknown session {sid} disconnected")


@sio.event
async def join_alert(sid, data):
    """
    Join an alert room for real-time updates.
    
    Requirements: 5.4 - Real-time updates via Socket.io
    """
    user_id = SocketIOManager.get_user_id(sid)
    if not user_id:
        await sio.emit("error", {
            "code": "AUTH_REQUIRED",
            "message": "Authentication required"
        }, to=sid)
        return
    
    alert_id = data.get("alert_id") if isinstance(data, dict) else None
    if not alert_id:
        await sio.emit("error", {
            "code": "INVALID_REQUEST",
            "message": "alert_id is required"
        }, to=sid)
        return
    
    # Join the alert room
    room_name = f"alert:{alert_id}"
    await sio.enter_room(sid, room_name)
    RealtimeService.join_room(user_id, alert_id, sid)
    
    print(f"[Socket.io] User {user_id} joined alert room {alert_id}")
    
    # Send confirmation
    await sio.emit("joined_alert", {
        "success": True,
        "alert_id": alert_id,
        "message": "Joined alert channel"
    }, to=sid)


@sio.event
async def leave_alert(sid, data):
    """Leave an alert room."""
    user_id = SocketIOManager.get_user_id(sid)
    if not user_id:
        return
    
    alert_id = data.get("alert_id") if isinstance(data, dict) else None
    if not alert_id:
        return
    
    room_name = f"alert:{alert_id}"
    await sio.leave_room(sid, room_name)
    RealtimeService.leave_room(user_id, alert_id)
    
    print(f"[Socket.io] User {user_id} left alert room {alert_id}")
    
    await sio.emit("left_alert", {
        "success": True,
        "alert_id": alert_id,
    }, to=sid)


@sio.event
async def send_message(sid, data):
    """
    Send an encrypted message to an alert channel.
    
    Requirements: 5.1, 5.2 - End-to-end encrypted channels using AES-256-GCM
    """
    user_id = SocketIOManager.get_user_id(sid)
    if not user_id:
        await sio.emit("error", {
            "code": "AUTH_REQUIRED",
            "message": "Authentication required"
        }, to=sid)
        return
    
    # Validate data
    if not isinstance(data, dict):
        await sio.emit("error", {
            "code": "INVALID_REQUEST",
            "message": "Invalid message format"
        }, to=sid)
        return
    
    alert_id = data.get("alert_id")
    encrypted_payload = data.get("payload")
    
    if not alert_id or not encrypted_payload:
        await sio.emit("error", {
            "code": "INVALID_REQUEST",
            "message": "alert_id and payload are required"
        }, to=sid)
        return
    
    # Verify the payload is encrypted
    if not isinstance(encrypted_payload, dict) or not encrypted_payload.get("encrypted"):
        await sio.emit("error", {
            "code": "ENCRYPTION_REQUIRED",
            "message": "Message payload must be encrypted"
        }, to=sid)
        return
    
    # Broadcast encrypted message to alert room
    room_name = f"alert:{alert_id}"
    
    # Create the broadcast payload
    broadcast_data = {
        "type": "chat_message",
        "alert_id": alert_id,
        "sender_id": user_id,
        "payload": encrypted_payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    # Broadcast to all users in the room (including sender for confirmation)
    await sio.emit("message", broadcast_data, room=room_name)
    
    print(f"[Socket.io] Message sent to alert {alert_id} by user {user_id}")


@sio.event
async def send_alert_update(sid, data):
    """
    Send an encrypted alert status update.
    
    Requirements: 5.4 - Real-time updates via Socket.io with encrypted payloads
    """
    user_id = SocketIOManager.get_user_id(sid)
    if not user_id:
        await sio.emit("error", {
            "code": "AUTH_REQUIRED",
            "message": "Authentication required"
        }, to=sid)
        return
    
    if not isinstance(data, dict):
        await sio.emit("error", {
            "code": "INVALID_REQUEST",
            "message": "Invalid update format"
        }, to=sid)
        return
    
    alert_id = data.get("alert_id")
    encrypted_payload = data.get("payload")
    
    if not alert_id or not encrypted_payload:
        await sio.emit("error", {
            "code": "INVALID_REQUEST",
            "message": "alert_id and payload are required"
        }, to=sid)
        return
    
    # Verify encryption
    if not isinstance(encrypted_payload, dict) or not encrypted_payload.get("encrypted"):
        await sio.emit("error", {
            "code": "ENCRYPTION_REQUIRED",
            "message": "Update payload must be encrypted"
        }, to=sid)
        return
    
    room_name = f"alert:{alert_id}"
    
    broadcast_data = {
        "type": "alert_update",
        "alert_id": alert_id,
        "sender_id": user_id,
        "payload": encrypted_payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    await sio.emit("alert_update", broadcast_data, room=room_name)
    
    print(f"[Socket.io] Alert update sent for {alert_id} by user {user_id}")


# Helper functions for broadcasting from other parts of the application

async def broadcast_alert_update(
    alert_id: str,
    status: str,
    data: Optional[dict] = None,
    encrypt: bool = True
) -> None:
    """
    Broadcast an alert status update to all connected users in the alert room.
    
    Requirements: 5.4 - Real-time updates via Socket.io with encrypted payloads
    """
    room_name = f"alert:{alert_id}"
    
    if encrypt:
        payload = SocketIOEncryption.encrypt_alert_update(
            alert_id=alert_id,
            status=status,
            data=data
        )
    else:
        payload = {
            "encrypted": False,
            "type": "alert_update",
            "alert_id": alert_id,
            "status": status,
            "data": data or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    broadcast_data = {
        "type": "alert_update",
        "alert_id": alert_id,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    await sio.emit("alert_update", broadcast_data, room=room_name)


async def broadcast_chat_message(
    alert_id: str,
    sender_id: str,
    content: str,
    encrypt: bool = True
) -> None:
    """
    Broadcast a chat message to all connected users in the alert room.
    
    Requirements: 5.1, 5.2 - End-to-end encrypted channels
    """
    room_name = f"alert:{alert_id}"
    
    if encrypt:
        payload = SocketIOEncryption.encrypt_chat_message(
            alert_id=alert_id,
            sender_id=sender_id,
            content=content
        )
    else:
        payload = {
            "encrypted": False,
            "type": "chat_message",
            "alert_id": alert_id,
            "sender_id": sender_id,
            "content": content,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
    
    broadcast_data = {
        "type": "chat_message",
        "alert_id": alert_id,
        "sender_id": sender_id,
        "payload": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    await sio.emit("message", broadcast_data, room=room_name)


async def notify_user(
    user_id: str,
    event: str,
    data: dict,
    encrypt: bool = False
) -> None:
    """
    Send a notification to a specific user if they are connected.
    """
    # Find all sessions for this user
    for sid, session in SocketIOManager._sessions.items():
        if session.get("user_id") == user_id and session.get("authenticated"):
            if encrypt:
                payload = SocketIOEncryption.encrypt_message(data)
                await sio.emit(event, {"encrypted": True, "payload": payload}, to=sid)
            else:
                await sio.emit(event, data, to=sid)
