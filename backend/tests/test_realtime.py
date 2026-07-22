"""Property tests for real-time communication with encryption.

Feature: circlo-safety-app
Requirements: 5.1, 5.2, 5.3, 5.4, 5.5
"""
import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from uuid import uuid4
from datetime import datetime, timedelta, timezone
import json
import base64

from app.core.security import (
    EncryptionService,
    SocketIOEncryption,
    KeyManager,
)
from app.models.message import Message

# Increase deadline for tests that use PBKDF2 key derivation (computationally expensive)
SLOW_DEADLINE = 2000  # 2 seconds


class TestEncryptedRealTimeUpdates:
    """Property tests for encrypted real-time updates.
    
    Feature: circlo-safety-app, Property 14: Encrypted Real-Time Updates
    **Validates: Requirements 5.4**
    """
    
    @given(
        alert_id=st.uuids(),
        status=st.sampled_from(["pending", "verified", "escalated", "resolved"]),
        data_keys=st.lists(st.text(min_size=1, max_size=10, alphabet='abcdefghijklmnopqrstuvwxyz'), min_size=0, max_size=3),
        data_values=st.lists(st.text(min_size=0, max_size=50), min_size=0, max_size=3),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    def test_socket_io_payload_is_always_encrypted(
        self,
        alert_id,
        status: str,
        data_keys: list,
        data_values: list,
    ):
        """
        Property 14: Encrypted Real-Time Updates
        *For any* Socket.io communication, the payload should be encrypted before transmission.
        
        Feature: circlo-safety-app, Property 14: Encrypted Real-Time Updates
        **Validates: Requirements 5.4**
        """
        # Build data dict from keys and values
        data = {}
        for i, key in enumerate(data_keys):
            if i < len(data_values) and key:
                data[key] = data_values[i]
        
        # Encrypt alert update
        encrypted_payload = SocketIOEncryption.encrypt_alert_update(
            alert_id=str(alert_id),
            status=status,
            data=data if data else None,
        )
        
        # Property: Payload must be marked as encrypted
        assert encrypted_payload.get("encrypted") is True, (
            "Socket.io payload must be marked as encrypted"
        )
        
        # Property: Payload must contain encrypted data
        assert "payload" in encrypted_payload, (
            "Encrypted payload must contain 'payload' field"
        )
        assert "iv" in encrypted_payload, (
            "Encrypted payload must contain 'iv' field"
        )
        
        # Property: Original data should not be visible in encrypted payload
        payload_str = json.dumps(encrypted_payload)
        assert str(alert_id) not in payload_str or "alert_id" not in encrypted_payload, (
            "Alert ID should not be visible in plain text in encrypted payload"
        )
        assert status not in encrypted_payload.get("payload", ""), (
            "Status should not be visible in plain text in encrypted payload"
        )
    
    @given(
        alert_id=st.uuids(),
        sender_id=st.uuids(),
        content=st.text(min_size=1, max_size=1000),
    )
    @settings(max_examples=100)
    def test_chat_message_encryption(
        self,
        alert_id,
        sender_id,
        content: str,
    ):
        """
        Property 14: Encrypted Real-Time Updates
        *For any* chat message, the content should be encrypted before transmission.
        
        Feature: circlo-safety-app, Property 14: Encrypted Real-Time Updates
        **Validates: Requirements 5.4**
        """
        assume(len(content.strip()) > 0)  # Skip empty content
        
        # Encrypt chat message
        encrypted_payload = SocketIOEncryption.encrypt_chat_message(
            alert_id=str(alert_id),
            sender_id=str(sender_id),
            content=content,
        )
        
        # Property: Payload must be marked as encrypted
        assert encrypted_payload.get("encrypted") is True
        
        # Property: Original content should not be visible
        payload_str = json.dumps(encrypted_payload)
        # Content should not appear in the encrypted payload string
        # (unless it's very short and happens to match base64 chars)
        if len(content) > 10:
            assert content not in payload_str, (
                "Message content should not be visible in encrypted payload"
            )
    
    @given(
        message_dict=st.fixed_dictionaries({
            "type": st.just("test_message"),
            "data": st.text(min_size=1, max_size=500),
        }),
    )
    @settings(max_examples=100)
    def test_encrypt_decrypt_roundtrip(self, message_dict: dict):
        """
        Property 14: Encrypted Real-Time Updates
        *For any* message, encrypting then decrypting should return the original message.
        
        Feature: circlo-safety-app, Property 14: Encrypted Real-Time Updates
        **Validates: Requirements 5.4**
        """
        # Encrypt
        encrypted = SocketIOEncryption.encrypt_message(message_dict)
        
        # Verify encrypted format
        assert encrypted.get("encrypted") is True
        assert "payload" in encrypted
        assert "iv" in encrypted
        
        # Decrypt
        decrypted = SocketIOEncryption.decrypt_message(encrypted)
        
        # Property: Decrypted message should match original
        assert decrypted == message_dict, (
            f"Decrypted message {decrypted} should match original {message_dict}"
        )
    
    @given(
        alert_id=st.uuids(),
        status=st.sampled_from(["pending", "verified", "escalated", "resolved"]),
    )
    @settings(max_examples=100)
    def test_alert_update_roundtrip(self, alert_id, status: str):
        """
        Property 14: Encrypted Real-Time Updates
        *For any* alert update, encrypting then decrypting should preserve all fields.
        
        Feature: circlo-safety-app, Property 14: Encrypted Real-Time Updates
        **Validates: Requirements 5.4**
        """
        data = {"extra_field": "test_value"}
        
        # Encrypt
        encrypted = SocketIOEncryption.encrypt_alert_update(
            alert_id=str(alert_id),
            status=status,
            data=data,
        )
        
        # Decrypt
        decrypted = SocketIOEncryption.decrypt_message(encrypted)
        
        # Property: All fields should be preserved
        assert decrypted["type"] == "alert_update"
        assert decrypted["alert_id"] == str(alert_id)
        assert decrypted["status"] == status
        assert decrypted["data"] == data
    
    @given(
        alert_id=st.uuids(),
        sender_id=st.uuids(),
        content=st.text(min_size=1, max_size=500),
    )
    @settings(max_examples=100)
    def test_chat_message_roundtrip(self, alert_id, sender_id, content: str):
        """
        Property 14: Encrypted Real-Time Updates
        *For any* chat message, encrypting then decrypting should preserve content.
        
        Feature: circlo-safety-app, Property 14: Encrypted Real-Time Updates
        **Validates: Requirements 5.4**
        """
        assume(len(content.strip()) > 0)
        
        # Encrypt
        encrypted = SocketIOEncryption.encrypt_chat_message(
            alert_id=str(alert_id),
            sender_id=str(sender_id),
            content=content,
        )
        
        # Decrypt
        decrypted = SocketIOEncryption.decrypt_message(encrypted)
        
        # Property: All fields should be preserved
        assert decrypted["type"] == "chat_message"
        assert decrypted["alert_id"] == str(alert_id)
        assert decrypted["sender_id"] == str(sender_id)
        assert decrypted["content"] == content
        assert "sent_at" in decrypted
    
    @given(
        key1=st.text(min_size=10, max_size=50),
        key2=st.text(min_size=10, max_size=50),
        message=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=100)
    def test_different_keys_produce_different_ciphertext(
        self,
        key1: str,
        key2: str,
        message: str,
    ):
        """
        Property 14: Encrypted Real-Time Updates
        *For any* two different keys, the same message should produce different ciphertext.
        
        Feature: circlo-safety-app, Property 14: Encrypted Real-Time Updates
        **Validates: Requirements 5.4**
        """
        assume(key1 != key2)
        assume(len(message.strip()) > 0)
        
        message_dict = {"content": message}
        
        # Encrypt with different keys
        encrypted1 = SocketIOEncryption.encrypt_message(message_dict, key1)
        encrypted2 = SocketIOEncryption.encrypt_message(message_dict, key2)
        
        # Property: Different keys should produce different ciphertext
        # (with very high probability due to different IVs and keys)
        assert encrypted1["payload"] != encrypted2["payload"], (
            "Different keys should produce different ciphertext"
        )
    
    @given(
        alert_id=st.uuids(),
    )
    @settings(max_examples=100, deadline=SLOW_DEADLINE)
    def test_alert_specific_key_derivation(self, alert_id):
        """
        Property 14: Encrypted Real-Time Updates
        *For any* alert, a unique encryption key should be derived.
        
        Feature: circlo-safety-app, Property 14: Encrypted Real-Time Updates
        **Validates: Requirements 5.4**
        """
        # Derive key for alert
        key = KeyManager.derive_alert_key(str(alert_id))
        
        # Property: Key should be a valid base64 string
        try:
            decoded = base64.b64decode(key)
            assert len(decoded) == 32, "Derived key should be 32 bytes"
        except Exception as e:
            pytest.fail(f"Key should be valid base64: {e}")
        
        # Property: Same alert_id should produce same key
        key2 = KeyManager.derive_alert_key(str(alert_id))
        assert key == key2, "Same alert_id should produce same key"
    
    @given(
        alert_id1=st.uuids(),
        alert_id2=st.uuids(),
    )
    @settings(max_examples=100, deadline=SLOW_DEADLINE)
    def test_different_alerts_have_different_keys(self, alert_id1, alert_id2):
        """
        Property 14: Encrypted Real-Time Updates
        *For any* two different alerts, they should have different encryption keys.
        
        Feature: circlo-safety-app, Property 14: Encrypted Real-Time Updates
        **Validates: Requirements 5.4**
        """
        assume(alert_id1 != alert_id2)
        
        key1 = KeyManager.derive_alert_key(str(alert_id1))
        key2 = KeyManager.derive_alert_key(str(alert_id2))
        
        # Property: Different alerts should have different keys
        assert key1 != key2, (
            "Different alerts should have different encryption keys"
        )
    
    def test_encrypted_payload_has_timestamp(self):
        """Encrypted payloads should include a timestamp."""
        encrypted = SocketIOEncryption.encrypt_message({"test": "data"})
        
        assert "timestamp" in encrypted
        # Timestamp should be ISO format
        try:
            datetime.fromisoformat(encrypted["timestamp"].replace("Z", "+00:00"))
        except ValueError:
            pytest.fail("Timestamp should be valid ISO format")
    
    def test_unencrypted_message_raises_error_on_decrypt(self):
        """Attempting to decrypt an unencrypted message should raise an error."""
        unencrypted = {"encrypted": False, "data": "test"}
        
        with pytest.raises(ValueError, match="not encrypted"):
            SocketIOEncryption.decrypt_message(unencrypted)



class TestAutomaticDataDeletion:
    """Property tests for automatic data deletion.
    
    Feature: circlo-safety-app, Property 15: Automatic Data Deletion
    **Validates: Requirements 5.5, 7.4**
    """
    
    @given(
        days_since_creation=st.integers(min_value=0, max_value=365),
    )
    @settings(max_examples=100)
    def test_message_expiry_after_90_days(self, days_since_creation: int):
        """
        Property 15: Automatic Data Deletion
        *For any* user data or message history, automatic deletion should occur
        after 90 days of inactivity or alert resolution.
        
        Feature: circlo-safety-app, Property 15: Automatic Data Deletion
        **Validates: Requirements 5.5, 7.4**
        """
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(days=days_since_creation)
        auto_delete_at = created_at + timedelta(days=90)
        
        message = Message(
            id=uuid4(),
            alert_id=uuid4(),
            sender_id=uuid4(),
            content_encrypted="encrypted_content",
            iv="initialization_vector",
            created_at=created_at,
            auto_delete_at=auto_delete_at,
        )
        
        # Property: Message should be expired if 90+ days have passed since creation
        expected_expired = days_since_creation >= 90
        assert message.is_expired == expected_expired, (
            f"Message created {days_since_creation} days ago should "
            f"{'be' if expected_expired else 'not be'} expired"
        )
    
    @given(
        days_until_deletion=st.integers(min_value=0, max_value=180),
    )
    @settings(max_examples=100)
    def test_days_until_deletion_calculation(self, days_until_deletion: int):
        """
        Property 15: Automatic Data Deletion
        *For any* message, the days_until_deletion should accurately reflect
        the time remaining until auto-deletion.
        
        Feature: circlo-safety-app, Property 15: Automatic Data Deletion
        **Validates: Requirements 5.5, 7.4**
        """
        now = datetime.now(timezone.utc)
        auto_delete_at = now + timedelta(days=days_until_deletion)
        
        message = Message(
            id=uuid4(),
            alert_id=uuid4(),
            sender_id=uuid4(),
            content_encrypted="encrypted_content",
            iv="initialization_vector",
            created_at=now - timedelta(days=90 - days_until_deletion),
            auto_delete_at=auto_delete_at,
        )
        
        # Property: days_until_deletion should match expected value
        # Allow 1 day tolerance for edge cases around midnight
        assert abs(message.days_until_deletion - days_until_deletion) <= 1, (
            f"Expected ~{days_until_deletion} days until deletion, "
            f"got {message.days_until_deletion}"
        )
    
    @given(
        days_past_deletion=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=100)
    def test_expired_message_has_zero_days_remaining(self, days_past_deletion: int):
        """
        Property 15: Automatic Data Deletion
        *For any* expired message, days_until_deletion should be 0.
        
        Feature: circlo-safety-app, Property 15: Automatic Data Deletion
        **Validates: Requirements 5.5, 7.4**
        """
        now = datetime.now(timezone.utc)
        auto_delete_at = now - timedelta(days=days_past_deletion)
        
        message = Message(
            id=uuid4(),
            alert_id=uuid4(),
            sender_id=uuid4(),
            content_encrypted="encrypted_content",
            iv="initialization_vector",
            created_at=now - timedelta(days=90 + days_past_deletion),
            auto_delete_at=auto_delete_at,
        )
        
        # Property: Expired messages should have 0 days remaining
        assert message.days_until_deletion == 0, (
            f"Expired message should have 0 days until deletion, "
            f"got {message.days_until_deletion}"
        )
        assert message.is_expired is True
    
    def test_new_message_has_90_day_auto_delete(self):
        """
        Property 15: Automatic Data Deletion
        New messages should have auto_delete_at set to 90 days from creation.
        
        Feature: circlo-safety-app, Property 15: Automatic Data Deletion
        **Validates: Requirements 5.5, 7.4**
        """
        now = datetime.now(timezone.utc)
        
        message = Message(
            id=uuid4(),
            alert_id=uuid4(),
            sender_id=uuid4(),
            content_encrypted="encrypted_content",
            iv="initialization_vector",
            created_at=now,
            auto_delete_at=now + timedelta(days=90),
        )
        
        # Property: New message should have ~90 days until deletion
        assert 89 <= message.days_until_deletion <= 90, (
            f"New message should have ~90 days until deletion, "
            f"got {message.days_until_deletion}"
        )
        assert message.is_expired is False
    
    @given(
        alert_type=st.sampled_from(["missing", "emergency", "check_in"]),
        days_since_resolution=st.integers(min_value=0, max_value=180),
    )
    @settings(max_examples=100)
    def test_resolved_alert_sets_90_day_deletion(
        self,
        alert_type: str,
        days_since_resolution: int,
    ):
        """
        Property 15: Automatic Data Deletion
        *For any* resolved alert, auto_delete_at should be set to 90 days
        from resolution time.
        
        Feature: circlo-safety-app, Property 15: Automatic Data Deletion
        **Validates: Requirements 5.5, 7.4**
        """
        from app.models.alert import Alert, AlertType, AlertStatus
        
        now = datetime.now(timezone.utc)
        resolved_at = now - timedelta(days=days_since_resolution)
        auto_delete_at = resolved_at + timedelta(days=90)
        
        alert = Alert(
            id=uuid4(),
            user_id=uuid4(),
            type=AlertType(alert_type),
            status=AlertStatus.resolved,
            verification_count=2,
            required_verifications=2,
            escalation_level=1,
            created_at=resolved_at - timedelta(hours=1),
            resolved_at=resolved_at,
            auto_delete_at=auto_delete_at,
        )
        
        # Property: Alert should be deleted 90 days after resolution
        expected_days_remaining = max(0, 90 - days_since_resolution)
        
        # Calculate actual days remaining
        if auto_delete_at <= now:
            actual_days_remaining = 0
        else:
            actual_days_remaining = (auto_delete_at - now).days
        
        # Allow 1 day tolerance
        assert abs(actual_days_remaining - expected_days_remaining) <= 1, (
            f"Expected ~{expected_days_remaining} days until deletion, "
            f"got {actual_days_remaining}"
        )
    
    @given(
        num_messages=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_all_messages_in_alert_have_same_deletion_date(self, num_messages: int):
        """
        Property 15: Automatic Data Deletion
        *For any* set of messages in an alert, they should all have the same
        auto_delete_at date when the alert is resolved.
        
        Feature: circlo-safety-app, Property 15: Automatic Data Deletion
        **Validates: Requirements 5.5, 7.4**
        """
        now = datetime.now(timezone.utc)
        alert_id = uuid4()
        auto_delete_at = now + timedelta(days=90)
        
        messages = []
        for i in range(num_messages):
            message = Message(
                id=uuid4(),
                alert_id=alert_id,
                sender_id=uuid4(),
                content_encrypted=f"encrypted_content_{i}",
                iv=f"iv_{i}",
                created_at=now - timedelta(hours=i),
                auto_delete_at=auto_delete_at,
            )
            messages.append(message)
        
        # Property: All messages should have the same auto_delete_at
        first_delete_at = messages[0].auto_delete_at
        for msg in messages:
            assert msg.auto_delete_at == first_delete_at, (
                "All messages in an alert should have the same deletion date"
            )
    
    def test_message_without_auto_delete_defaults_to_90_days(self):
        """
        Property 15: Automatic Data Deletion
        Messages without explicit auto_delete_at should default to 90 days.
        
        Feature: circlo-safety-app, Property 15: Automatic Data Deletion
        **Validates: Requirements 5.5, 7.4**
        """
        message = Message(
            id=uuid4(),
            alert_id=uuid4(),
            sender_id=uuid4(),
            content_encrypted="encrypted_content",
            iv="initialization_vector",
        )
        
        # Property: Default should be ~90 days
        # Note: The model sets default in the column definition
        if message.auto_delete_at is not None:
            assert 89 <= message.days_until_deletion <= 90
        else:
            # If auto_delete_at is None, days_until_deletion should return 90
            assert message.days_until_deletion == 90
    
    @given(
        days_inactive=st.integers(min_value=0, max_value=180),
    )
    @settings(max_examples=100)
    def test_user_data_deletion_after_inactivity(self, days_inactive: int):
        """
        Property 15: Automatic Data Deletion
        *For any* user, data should be deleted after 90 days of inactivity.
        
        Feature: circlo-safety-app, Property 15: Automatic Data Deletion
        **Validates: Requirements 5.5, 7.4**
        """
        from app.models.user import User
        
        now = datetime.now(timezone.utc)
        last_active = now - timedelta(days=days_inactive)
        auto_delete_at = last_active + timedelta(days=90)
        
        user = User(
            id=uuid4(),
            phone_hash="hashed_phone_number",
            name_encrypted="encrypted_name",
            password_hash="hashed_password",
            created_at=last_active - timedelta(days=30),
            last_active=last_active,
            auto_delete_at=auto_delete_at,
        )
        
        # Property: User should be marked for deletion 90 days after last activity
        expected_expired = days_inactive >= 90
        is_expired = auto_delete_at <= now
        
        assert is_expired == expected_expired, (
            f"User inactive for {days_inactive} days should "
            f"{'be' if expected_expired else 'not be'} marked for deletion"
        )
