"""Property tests for notification service.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
- Push notifications via Firebase Cloud Messaging
- Encrypted notification payloads
- Priority-based notifications by circle type
- Offline notification queuing
- User notification preferences
"""
import pytest
from hypothesis import given, strategies as st, settings
from datetime import datetime, timezone
import json

from app.core.security import EncryptionService
from app.models.notification import NotificationPriority, NotificationType
from app.models.circle import CircleType
from app.services.notification_service import (
    NotificationService,
    CIRCLE_TYPE_PRIORITY,
    FCM_PRIORITY_MAP,
)


class TestEncryptedNotifications:
    """Property tests for encrypted push notifications.
    
    Feature: circlo-safety-app, Property 19: Encrypted Push Notifications
    **Validates: Requirements 8.1, 8.2**
    """
    
    @given(
        title=st.text(min_size=1, max_size=100),
        body=st.text(min_size=1, max_size=500),
    )
    @settings(max_examples=100)
    def test_notification_content_encryption_round_trip(self, title: str, body: str):
        """Property 19: Encrypted notification content should decrypt correctly.
        
        For any notification title and body, encrypting then decrypting
        should produce the original content.
        """
        # Encrypt the content
        title_encrypted, body_encrypted, data_encrypted, iv = \
            NotificationService._encrypt_notification_content(title, body, None)
        
        # Decrypt the content
        decrypted_title, decrypted_body, decrypted_data = \
            NotificationService._decrypt_notification_content(
                title_encrypted, body_encrypted, data_encrypted, iv
            )
        
        # Verify round trip
        assert decrypted_title == title
        assert decrypted_body == body
        assert decrypted_data is None
    
    @given(
        title=st.text(min_size=1, max_size=100),
        body=st.text(min_size=1, max_size=500),
        data=st.dictionaries(
            keys=st.text(min_size=1, max_size=20, alphabet=st.characters(
                whitelist_categories=('L', 'N')
            )),
            values=st.text(min_size=0, max_size=50),
            min_size=0,
            max_size=5
        )
    )
    @settings(max_examples=100)
    def test_notification_with_data_encryption_round_trip(
        self, title: str, body: str, data: dict
    ):
        """Notification with additional data should encrypt/decrypt correctly."""
        # Encrypt the content with data
        title_encrypted, body_encrypted, data_encrypted, iv = \
            NotificationService._encrypt_notification_content(title, body, data)
        
        # Decrypt the content
        decrypted_title, decrypted_body, decrypted_data = \
            NotificationService._decrypt_notification_content(
                title_encrypted, body_encrypted, data_encrypted, iv
            )
        
        # Verify round trip
        assert decrypted_title == title
        assert decrypted_body == body
        assert decrypted_data == data

    
    @given(
        title=st.text(min_size=5, max_size=100),
        body=st.text(min_size=5, max_size=500),
    )
    @settings(max_examples=100)
    def test_encrypted_content_does_not_contain_plaintext(self, title: str, body: str):
        """Encrypted content should not contain plaintext (for non-trivial inputs).
        
        For any notification with title and body of at least 5 characters,
        the encrypted ciphertext should not contain the original plaintext.
        """
        title_encrypted, body_encrypted, _, _ = \
            NotificationService._encrypt_notification_content(title, body, None)
        
        # Encrypted content should not contain plaintext
        assert title not in title_encrypted
        assert body not in body_encrypted
    
    @given(
        title=st.text(min_size=1, max_size=100),
        body=st.text(min_size=1, max_size=500),
    )
    @settings(max_examples=50)
    def test_different_ivs_for_same_content(self, title: str, body: str):
        """Each encryption should use different IV (semantic security).
        
        For any notification content, encrypting twice should produce
        different IVs, ensuring semantic security.
        """
        import json
        _, _, _, iv1_json = NotificationService._encrypt_notification_content(title, body, None)
        _, _, _, iv2_json = NotificationService._encrypt_notification_content(title, body, None)
        
        iv1 = json.loads(iv1_json)
        iv2 = json.loads(iv2_json)
        
        # IVs should be different for each encryption
        assert iv1["title_iv"] != iv2["title_iv"]
        assert iv1["body_iv"] != iv2["body_iv"]
    
    @given(
        title=st.text(min_size=1, max_size=100),
        body=st.text(min_size=1, max_size=500),
    )
    @settings(max_examples=50)
    def test_fcm_payload_is_encrypted(self, title: str, body: str):
        """FCM payload should contain encrypted data.
        
        For any notification, the FCM payload should be marked as encrypted
        and contain the encrypted payload and IV.
        """
        # Create a mock notification object
        class MockNotification:
            id = "test-notification-id"
            type = NotificationType.alert_created
            priority = NotificationPriority.high
            alert_id = None
            circle_id = None
            created_at = datetime.now(timezone.utc)
        
        notification = MockNotification()
        
        # Build FCM payload
        fcm_payload = NotificationService.build_fcm_payload(
            notification, title, body, None
        )
        
        # Verify payload structure
        assert fcm_payload["encrypted"] is True
        assert "payload" in fcm_payload
        assert "iv" in fcm_payload
        assert "notification_id" in fcm_payload
        assert "type" in fcm_payload
        assert "priority" in fcm_payload
        assert "timestamp" in fcm_payload
        
        # Verify the payload can be decrypted
        decrypted = EncryptionService.decrypt({
            "ciphertext": fcm_payload["payload"],
            "iv": fcm_payload["iv"]
        })
        
        payload_data = json.loads(decrypted)
        assert payload_data["title"] == title
        assert payload_data["body"] == body



class TestNotificationPriorities:
    """Property tests for notification priority by circle type.
    
    Feature: circlo-safety-app, Property 20: Notification Priority by Circle Type
    **Validates: Requirements 8.3**
    """
    
    def test_inner_circle_gets_critical_priority(self):
        """Inner Circle notifications should have critical priority.
        
        For any notification to Inner Circle members, the priority
        should be set to critical (highest priority).
        """
        priority = NotificationService.get_priority_for_circle_type(CircleType.inner)
        assert priority == NotificationPriority.critical
    
    def test_community_circle_gets_high_priority(self):
        """Community Circle notifications should have high priority.
        
        For any notification to Community Circle members, the priority
        should be set to high.
        """
        priority = NotificationService.get_priority_for_circle_type(CircleType.community)
        assert priority == NotificationPriority.high
    
    def test_professional_circle_gets_normal_priority(self):
        """Professional Circle notifications should have normal priority.
        
        For any notification to Professional Circle members, the priority
        should be set to normal.
        """
        priority = NotificationService.get_priority_for_circle_type(CircleType.professional)
        assert priority == NotificationPriority.normal
    
    @given(st.sampled_from(list(CircleType)))
    @settings(max_examples=100)
    def test_priority_ordering_is_consistent(self, circle_type: CircleType):
        """Property 20: Priority ordering should be consistent.
        
        For any circle type, the priority should follow the ordering:
        Inner Circle > Community Circle > Professional Circle
        """
        priority = NotificationService.get_priority_for_circle_type(circle_type)
        
        # Verify priority is valid
        assert priority in NotificationPriority
        
        # Verify priority mapping is correct
        expected = CIRCLE_TYPE_PRIORITY[circle_type]
        assert priority == expected
    
    def test_priority_hierarchy(self):
        """Priority hierarchy should be maintained.
        
        Inner Circle priority should be higher than Community Circle,
        which should be higher than Professional Circle.
        """
        inner_priority = NotificationService.get_priority_for_circle_type(CircleType.inner)
        community_priority = NotificationService.get_priority_for_circle_type(CircleType.community)
        professional_priority = NotificationService.get_priority_for_circle_type(CircleType.professional)
        
        # Define priority order (critical > high > normal > low)
        priority_order = {
            NotificationPriority.critical: 4,
            NotificationPriority.high: 3,
            NotificationPriority.normal: 2,
            NotificationPriority.low: 1,
        }
        
        # Verify hierarchy
        assert priority_order[inner_priority] > priority_order[community_priority]
        assert priority_order[community_priority] > priority_order[professional_priority]
    
    @given(st.sampled_from(list(NotificationPriority)))
    @settings(max_examples=100)
    def test_fcm_priority_mapping(self, priority: NotificationPriority):
        """FCM priority mapping should be valid.
        
        For any notification priority, the FCM priority should be
        either 'high' or 'normal'.
        """
        fcm_priority = FCM_PRIORITY_MAP.get(priority, "normal")
        
        # FCM only supports 'high' and 'normal'
        assert fcm_priority in ["high", "normal"]
        
        # Critical and high should map to 'high'
        if priority in [NotificationPriority.critical, NotificationPriority.high]:
            assert fcm_priority == "high"
        else:
            assert fcm_priority == "normal"
    
    def test_all_circle_types_have_priority_mapping(self):
        """All circle types should have a priority mapping.
        
        For any circle type, there should be a defined priority mapping.
        """
        for circle_type in CircleType:
            priority = NotificationService.get_priority_for_circle_type(circle_type)
            assert priority is not None
            assert priority in NotificationPriority
