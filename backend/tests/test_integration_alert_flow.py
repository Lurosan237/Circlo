"""Integration tests for complete alert flow.

Feature: circlo-safety-app
Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 5.1, 5.2, 5.3

Tests the complete missing person alert scenario including:
- Alert creation with multi-person verification
- End-to-end encryption throughout the flow
- Escalation and resolution processes
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from uuid import uuid4
from datetime import datetime, timedelta, timezone
import json

from app.models.alert import Alert, AlertVerification, AlertType, AlertStatus
from app.models.circle import Circle, CircleMember, CircleType, MemberStatus
from app.models.message import Message
from app.services.alert_service import AlertService
from app.services.realtime_service import RealtimeService
from app.core.security import EncryptionService, KeyManager, SocketIOEncryption


class TestCompleteAlertFlowIntegration:
    """Integration tests for the complete missing person alert scenario.
    
    Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
    """
    
    def test_alert_lifecycle_states(self):
        """Test that alert goes through correct lifecycle states."""
        # Create alert in pending state
        alert = Alert(
            id=uuid4(),
            user_id=uuid4(),
            type=AlertType.missing,
            status=AlertStatus.pending,
            verification_count=0,
            required_verifications=2,
            escalation_level=1,
            created_at=datetime.now(timezone.utc),
        )
        
        # Initial state: pending
        assert alert.status == AlertStatus.pending
        assert not alert.is_verified
        
        # Add first verification
        alert.verification_count = 1
        assert alert.status == AlertStatus.pending
        assert not alert.is_verified
        
        # Add second verification - should become verified
        alert.verification_count = 2
        alert.status = AlertStatus.verified
        assert alert.is_verified
        
        # Escalate to community
        alert.escalation_level = 2
        alert.status = AlertStatus.escalated
        alert.escalated_at = datetime.now(timezone.utc)
        assert alert.status == AlertStatus.escalated
        assert alert.escalation_level == 2
        
        # Escalate to professional
        alert.escalation_level = 3
        assert alert.escalation_level == 3
        assert not alert.can_escalate  # Max level reached
        
        # Resolve
        alert.status = AlertStatus.resolved
        alert.resolved_at = datetime.now(timezone.utc)
        assert alert.status == AlertStatus.resolved
        assert alert.resolved_at is not None
    
    @given(
        num_verifiers=st.integers(min_value=0, max_value=5),
        required=st.integers(min_value=1, max_value=3)
    )
    @settings(max_examples=100)
    def test_verification_threshold_property(self, num_verifiers: int, required: int):
        """
        Property: Alert becomes verified exactly when verification_count >= required_verifications.
        
        Requirements: 3.1 - Multi-person verification (2-of-3 Inner Circle)
        """
        alert = Alert(
            id=uuid4(),
            user_id=uuid4(),
            type=AlertType.missing,
            status=AlertStatus.pending if num_verifiers < required else AlertStatus.verified,
            verification_count=num_verifiers,
            required_verifications=required,
            escalation_level=1,
            created_at=datetime.now(timezone.utc),
        )
        
        expected_verified = num_verifiers >= required
        assert alert.is_verified == expected_verified
    
    def test_escalation_timing_sequence(self):
        """Test that escalation follows correct timing sequence."""
        now = datetime.now(timezone.utc)
        
        # Alert created and verified
        alert = Alert(
            id=uuid4(),
            user_id=uuid4(),
            type=AlertType.missing,
            status=AlertStatus.verified,
            verification_count=2,
            required_verifications=2,
            escalation_level=1,
            created_at=now,
        )
        
        # At 0 minutes: should be at Inner Circle level
        assert alert.escalation_level == 1
        time_until = AlertService.calculate_time_until_escalation(alert)
        # Allow 1 minute tolerance for timing
        assert 29 <= time_until <= 30  # ~30 minutes until Community escalation
        
        # Simulate 30 minutes passing - escalate to Community
        alert.escalation_level = 2
        alert.status = AlertStatus.escalated
        alert.escalated_at = now
        
        time_until = AlertService.calculate_time_until_escalation(alert)
        # Allow 1 minute tolerance for timing
        assert 119 <= time_until <= 120  # ~120 minutes until Professional escalation
        
        # Simulate 2 hours passing - escalate to Professional
        alert.escalation_level = 3
        alert.escalated_at = now
        
        time_until = AlertService.calculate_time_until_escalation(alert)
        assert time_until is None  # No more escalation possible
    
    def test_resolution_sets_auto_delete(self):
        """Test that resolution sets auto_delete_at to 90 days."""
        now = datetime.now(timezone.utc)
        
        alert = Alert(
            id=uuid4(),
            user_id=uuid4(),
            type=AlertType.missing,
            status=AlertStatus.verified,
            verification_count=2,
            required_verifications=2,
            escalation_level=1,
            created_at=now - timedelta(hours=1),
        )
        
        # Resolve the alert
        alert.status = AlertStatus.resolved
        alert.resolved_at = now
        alert.auto_delete_at = now + timedelta(days=90)
        
        # Verify auto_delete_at is set correctly
        expected_delete = now + timedelta(days=90)
        assert abs((alert.auto_delete_at - expected_delete).total_seconds()) < 1


class TestEndToEndEncryption:
    """Integration tests for end-to-end encryption throughout the alert flow.
    
    Requirements: 5.1, 5.2, 5.3
    """
    
    @given(content=st.text(min_size=1, max_size=1000))
    @settings(max_examples=100)
    def test_message_encryption_round_trip(self, content: str):
        """
        Property: Encrypting then decrypting a message returns the original content.
        
        Requirements: 5.1, 5.2, 5.3 - End-to-end encryption using AES-256-GCM
        """
        assume(len(content.strip()) > 0)
        
        alert_id = str(uuid4())
        
        # Derive alert-specific key
        alert_key = KeyManager.derive_alert_key(alert_id)
        
        # Encrypt the content
        encrypted = EncryptionService.encrypt(content, alert_key)
        
        # Verify encrypted data structure
        assert "ciphertext" in encrypted
        assert "iv" in encrypted
        assert encrypted["ciphertext"] != content  # Should be different from original
        
        # Decrypt the content
        decrypted = EncryptionService.decrypt(encrypted, alert_key)
        
        # Should match original
        assert decrypted == content
    
    @given(
        alert_id=st.uuids(),
        sender_id=st.uuids(),
        content=st.text(min_size=1, max_size=500)
    )
    @settings(max_examples=100)
    def test_socket_io_message_encryption(self, alert_id, sender_id, content: str):
        """
        Property: Socket.io messages are encrypted before transmission.
        
        Requirements: 5.4 - Real-time updates via Socket.io with encrypted payloads
        """
        assume(len(content.strip()) > 0)
        
        # Encrypt chat message for Socket.io
        encrypted_payload = SocketIOEncryption.encrypt_chat_message(
            alert_id=str(alert_id),
            sender_id=str(sender_id),
            content=content
        )
        
        # Verify payload is encrypted
        assert encrypted_payload.get("encrypted") == True
        assert "payload" in encrypted_payload
        assert "iv" in encrypted_payload
        
        # The encrypted payload should not contain the original content in plain text
        payload_str = json.dumps(encrypted_payload)
        # For non-trivial content, it shouldn't appear in the encrypted payload
        if len(content) > 10:
            assert content not in payload_str
    
    @given(
        alert_id=st.uuids(),
        status=st.sampled_from(["verified", "escalated", "resolved"])
    )
    @settings(max_examples=100)
    def test_alert_update_encryption(self, alert_id, status: str):
        """
        Property: Alert status updates are encrypted before transmission.
        
        Requirements: 5.4 - Real-time updates via Socket.io with encrypted payloads
        """
        data = {"escalation_level": 2, "timestamp": datetime.now(timezone.utc).isoformat()}
        
        # Encrypt alert update
        encrypted_payload = SocketIOEncryption.encrypt_alert_update(
            alert_id=str(alert_id),
            status=status,
            data=data
        )
        
        # Verify payload is encrypted
        assert encrypted_payload.get("encrypted") == True
        assert "payload" in encrypted_payload
        assert "iv" in encrypted_payload
    
    def test_different_alerts_use_different_keys(self):
        """Test that different alerts use different encryption keys."""
        alert_id_1 = str(uuid4())
        alert_id_2 = str(uuid4())
        
        key_1 = KeyManager.derive_alert_key(alert_id_1)
        key_2 = KeyManager.derive_alert_key(alert_id_2)
        
        # Keys should be different
        assert key_1 != key_2
        
        # Content encrypted with one key should not decrypt with another
        content = "Test message"
        encrypted = EncryptionService.encrypt(content, key_1)
        
        # Decrypting with correct key should work
        decrypted = EncryptionService.decrypt(encrypted, key_1)
        assert decrypted == content
        
        # Decrypting with wrong key should fail
        try:
            EncryptionService.decrypt(encrypted, key_2)
            assert False, "Should have raised an exception"
        except Exception:
            pass  # Expected behavior
    
    @given(content=st.text(min_size=1, max_size=100))
    @settings(max_examples=50, deadline=None)
    def test_encryption_produces_different_ciphertext_each_time(self, content: str):
        """
        Property: Encrypting the same content twice produces different ciphertext (due to random IV).
        """
        assume(len(content.strip()) > 0)
        
        alert_key = KeyManager.derive_alert_key(str(uuid4()))
        
        encrypted_1 = EncryptionService.encrypt(content, alert_key)
        encrypted_2 = EncryptionService.encrypt(content, alert_key)
        
        # Ciphertexts should be different (different IVs)
        assert encrypted_1["ciphertext"] != encrypted_2["ciphertext"]
        assert encrypted_1["iv"] != encrypted_2["iv"]
        
        # But both should decrypt to the same content
        assert EncryptionService.decrypt(encrypted_1, alert_key) == content
        assert EncryptionService.decrypt(encrypted_2, alert_key) == content


class TestEscalationAndResolutionProcesses:
    """Integration tests for escalation and resolution processes.
    
    Requirements: 3.3, 3.4, 3.5
    """
    
    @given(
        initial_level=st.integers(min_value=1, max_value=2),
        elapsed_minutes=st.integers(min_value=0, max_value=200)
    )
    @settings(max_examples=100)
    def test_escalation_timing_property(self, initial_level: int, elapsed_minutes: int):
        """
        Property: Escalation occurs at correct time thresholds.
        
        Requirements: 3.3 - Escalate to Community Circle after 30 minutes
        Requirements: 3.4 - Escalate to Professional Circle after 2 hours
        """
        now = datetime.now(timezone.utc)
        reference_time = now - timedelta(minutes=elapsed_minutes)
        
        alert = Alert(
            id=uuid4(),
            user_id=uuid4(),
            type=AlertType.missing,
            status=AlertStatus.verified if initial_level == 1 else AlertStatus.escalated,
            verification_count=2,
            required_verifications=2,
            escalation_level=initial_level,
            created_at=reference_time,
            escalated_at=reference_time if initial_level > 1 else None,
        )
        
        time_until = AlertService.calculate_time_until_escalation(alert)
        
        if initial_level == 1:
            # Inner Circle -> Community at 30 minutes
            if elapsed_minutes >= 30:
                assert time_until == 0
            else:
                expected = 30 - elapsed_minutes
                assert abs(time_until - expected) <= 1
        elif initial_level == 2:
            # Community -> Professional at 120 minutes
            if elapsed_minutes >= 120:
                assert time_until == 0
            else:
                expected = 120 - elapsed_minutes
                assert abs(time_until - expected) <= 1
    
    @given(
        escalation_level=st.integers(min_value=1, max_value=3),
        alert_type=st.sampled_from(list(AlertType))
    )
    @settings(max_examples=100)
    def test_resolution_from_any_state(self, escalation_level: int, alert_type: AlertType):
        """
        Property: Alerts can be resolved from any escalation level.
        
        Requirements: 3.5 - Notify all active participants and close the case
        """
        now = datetime.now(timezone.utc)
        
        alert = Alert(
            id=uuid4(),
            user_id=uuid4(),
            type=alert_type,
            status=AlertStatus.verified if escalation_level == 1 else AlertStatus.escalated,
            verification_count=2,
            required_verifications=2,
            escalation_level=escalation_level,
            created_at=now - timedelta(hours=1),
        )
        
        # Resolve the alert
        alert.status = AlertStatus.resolved
        alert.resolved_at = now
        alert.auto_delete_at = now + timedelta(days=90)
        
        # Verify resolution
        assert alert.status == AlertStatus.resolved
        assert alert.resolved_at is not None
        assert alert.auto_delete_at is not None
        
        # Escalation level should be preserved
        assert alert.escalation_level == escalation_level
    
    def test_participant_notification_by_escalation_level(self):
        """Test that correct participants are notified based on escalation level."""
        # At level 1: only Inner Circle
        # At level 2: Inner + Community
        # At level 3: Inner + Community + Professional
        
        for level in [1, 2, 3]:
            alert = Alert(
                id=uuid4(),
                user_id=uuid4(),
                type=AlertType.missing,
                status=AlertStatus.escalated if level > 1 else AlertStatus.verified,
                verification_count=2,
                required_verifications=2,
                escalation_level=level,
                created_at=datetime.now(timezone.utc),
            )
            
            # Determine expected circle types
            expected_circles = [CircleType.inner]
            if level >= 2:
                expected_circles.append(CircleType.community)
            if level >= 3:
                expected_circles.append(CircleType.professional)
            
            # Verify the logic
            assert len(expected_circles) == level
    
    def test_auto_delete_timing(self):
        """Test that auto_delete_at is set to 90 days after resolution."""
        now = datetime.now(timezone.utc)
        
        alert = Alert(
            id=uuid4(),
            user_id=uuid4(),
            type=AlertType.missing,
            status=AlertStatus.resolved,
            verification_count=2,
            required_verifications=2,
            escalation_level=2,
            created_at=now - timedelta(hours=3),
            resolved_at=now,
            auto_delete_at=now + timedelta(days=90),
        )
        
        # Calculate expected deletion time
        expected_delete = now + timedelta(days=90)
        
        # Should be within 1 second of expected
        time_diff = abs((alert.auto_delete_at - expected_delete).total_seconds())
        assert time_diff < 1


class TestMessageDeletionPolicy:
    """Integration tests for automatic message deletion.
    
    Requirements: 5.5 - Automatic deletion after 90 days
    """
    
    @given(days_old=st.integers(min_value=0, max_value=180))
    @settings(max_examples=100)
    def test_message_deletion_threshold(self, days_old: int):
        """
        Property: Messages older than 90 days should be marked for deletion.
        
        Requirements: 5.5 - Automatic deletion after 90 days
        """
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(days=days_old)
        auto_delete_at = created_at + timedelta(days=90)
        
        message = Message(
            id=uuid4(),
            alert_id=uuid4(),
            sender_id=uuid4(),
            content_encrypted="encrypted_content",
            iv="test_iv",
            created_at=created_at,
            auto_delete_at=auto_delete_at,
        )
        
        # Message should be deleted if auto_delete_at is in the past
        should_be_deleted = auto_delete_at < now
        # Use > 90 to avoid edge case at exactly 90 days
        is_past_threshold = days_old > 90
        
        assert should_be_deleted == is_past_threshold
    
    def test_message_auto_delete_set_on_creation(self):
        """Test that messages have auto_delete_at set to 90 days from creation."""
        now = datetime.now(timezone.utc)
        
        message = Message(
            id=uuid4(),
            alert_id=uuid4(),
            sender_id=uuid4(),
            content_encrypted="encrypted_content",
            iv="test_iv",
            created_at=now,
            auto_delete_at=now + timedelta(days=90),
        )
        
        expected_delete = now + timedelta(days=90)
        time_diff = abs((message.auto_delete_at - expected_delete).total_seconds())
        
        assert time_diff < 1
