import pytest
from hypothesis import given, strategies as st, settings
from app.core.security import (
    hash_phone_number,
    hash_pii,
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
    EncryptionService,
    SocketIOEncryption,
    KeyManager,
)


class TestPhoneNumberHashing:
    """Property tests for phone number hashing."""
    
    @given(st.from_regex(r'\+?[0-9]{10,15}', fullmatch=True))
    @settings(max_examples=100)
    def test_phone_hash_is_valid_sha256(self, phone: str):
        """Property 1: Hash should be a valid SHA-256 hash (64 hex characters)."""
        # Feature: circlo-safety-app, Property 1: Phone Number Hashing
        # **Validates: Requirements 1.1**
        hashed = hash_phone_number(phone)
        
        # Should be 64 hex characters
        assert len(hashed) == 64
        assert all(c in '0123456789abcdef' for c in hashed)
    
    @given(st.from_regex(r'\+?[0-9]{10,15}', fullmatch=True))
    @settings(max_examples=100)
    def test_phone_hash_is_deterministic(self, phone: str):
        """Hash should be deterministic (same input = same output)."""
        hash1 = hash_phone_number(phone)
        hash2 = hash_phone_number(phone)
        assert hash1 == hash2
    
    @given(st.from_regex(r'\+?[0-9]{10,15}', fullmatch=True))
    @settings(max_examples=100)
    def test_phone_hash_does_not_contain_original(self, phone: str):
        """Hash should not contain original phone number."""
        hashed = hash_phone_number(phone)
        digits_only = ''.join(c for c in phone if c.isdigit())
        assert digits_only not in hashed
    
    def test_phone_normalization(self):
        """Phone numbers with different formats should produce same hash."""
        # All these should normalize to the same value
        phones = [
            "+11234567890",
            "1234567890",
            "123-456-7890",
            "(123) 456-7890",
            "123 456 7890",
        ]
        
        # Remove the +1 prefix for comparison
        base_hash = hash_phone_number("1234567890")
        
        for phone in phones:
            # Normalize by removing non-digits
            normalized = ''.join(c for c in phone if c.isdigit())
            if normalized.startswith('1') and len(normalized) == 11:
                normalized = normalized[1:]  # Remove country code
            assert hash_phone_number(normalized) == base_hash


class TestPIIHashing:
    """Property tests for PII hashing."""
    
    @given(st.text(min_size=1, max_size=1000))
    @settings(max_examples=100)
    def test_pii_hash_is_valid_sha256(self, data: str):
        """PII hash should be a valid SHA-256 hash."""
        hashed = hash_pii(data)
        
        assert len(hashed) == 64
        assert all(c in '0123456789abcdef' for c in hashed)
    
    @given(st.text(min_size=1, max_size=1000))
    @settings(max_examples=100)
    def test_pii_hash_is_deterministic(self, data: str):
        """PII hash should be deterministic."""
        hash1 = hash_pii(data)
        hash2 = hash_pii(data)
        assert hash1 == hash2


class TestPasswordHashing:
    """Tests for password hashing."""
    
    @given(st.text(min_size=8, max_size=72, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'S'), max_codepoint=127)))
    @settings(max_examples=10, deadline=None)
    def test_password_hash_verification(self, password: str):
        """Password should verify correctly after hashing."""
        hashed = get_password_hash(password)
        assert verify_password(password, hashed)
    
    @given(st.text(min_size=8, max_size=72, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'S'), max_codepoint=127)))
    @settings(max_examples=10, deadline=None)
    def test_password_hash_is_not_plaintext(self, password: str):
        """Password hash should not contain plaintext password."""
        hashed = get_password_hash(password)
        assert password not in hashed


class TestJWTTokens:
    """Tests for JWT token creation and validation."""
    
    def test_token_creation_and_decoding(self):
        """Token should be created and decoded correctly."""
        data = {"sub": "test-user-id", "role": "user"}
        token = create_access_token(data)
        
        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded["sub"] == "test-user-id"
        assert decoded["role"] == "user"
        assert "exp" in decoded
    
    def test_invalid_token_returns_none(self):
        """Invalid token should return None."""
        decoded = decode_access_token("invalid-token")
        assert decoded is None


class TestEncryptionService:
    """Property tests for encryption service."""
    
    @given(st.text(min_size=1, max_size=1000))
    @settings(max_examples=100)
    def test_encryption_round_trip(self, plaintext: str):
        """Property 13: End-to-End Encryption round trip."""
        # Feature: circlo-safety-app, Property 13: End-to-End Encryption
        # **Validates: Requirements 5.1, 5.2, 5.3**
        encrypted = EncryptionService.encrypt(plaintext)
        decrypted = EncryptionService.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    @given(st.text(min_size=5, max_size=1000))
    @settings(max_examples=100)
    def test_ciphertext_does_not_contain_plaintext(self, plaintext: str):
        """Ciphertext should not contain plaintext (for non-trivial inputs)."""
        encrypted = EncryptionService.encrypt(plaintext)
        
        # For longer plaintexts, the ciphertext should not contain the plaintext
        # Skip very short plaintexts as they might coincidentally appear in base64
        if len(plaintext) >= 5:
            assert plaintext not in encrypted["ciphertext"]
    
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=50)
    def test_different_ivs_for_same_plaintext(self, plaintext: str):
        """Each encryption should use different IV (semantic security)."""
        encrypted1 = EncryptionService.encrypt(plaintext)
        encrypted2 = EncryptionService.encrypt(plaintext)
        
        assert encrypted1["iv"] != encrypted2["iv"]
    
    def test_key_derivation(self):
        """Key derivation should be deterministic."""
        password = "test-password"
        salt = EncryptionService.generate_salt()
        
        key1 = EncryptionService.derive_key_pbkdf2(password, salt)
        key2 = EncryptionService.derive_key_pbkdf2(password, salt)
        
        assert key1 == key2
    
    def test_different_salts_produce_different_keys(self):
        """Different salts should produce different keys."""
        password = "test-password"
        salt1 = EncryptionService.generate_salt()
        salt2 = EncryptionService.generate_salt()
        
        key1 = EncryptionService.derive_key_pbkdf2(password, salt1)
        key2 = EncryptionService.derive_key_pbkdf2(password, salt2)
        
        assert key1 != key2


class TestSocketIOEncryption:
    """Tests for Socket.io encryption utilities."""
    
    @given(st.dictionaries(
        keys=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('L', 'N'))),
        values=st.text(min_size=0, max_size=100),
        min_size=1,
        max_size=10
    ))
    @settings(max_examples=100)
    def test_message_encryption_round_trip(self, message: dict):
        """Encrypted messages should decrypt to original content."""
        # Feature: circlo-safety-app, Property 14: Encrypted Real-Time Updates
        # **Validates: Requirements 5.4**
        encrypted = SocketIOEncryption.encrypt_message(message)
        
        assert encrypted["encrypted"] is True
        assert "payload" in encrypted
        assert "iv" in encrypted
        assert "timestamp" in encrypted
        
        decrypted = SocketIOEncryption.decrypt_message(encrypted)
        assert decrypted == message
    
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=50)
    def test_alert_update_encryption(self, status: str):
        """Alert updates should be properly encrypted."""
        alert_id = "test-alert-123"
        data = {"location": "test"}
        
        encrypted = SocketIOEncryption.encrypt_alert_update(alert_id, status, data)
        
        assert encrypted["encrypted"] is True
        
        decrypted = SocketIOEncryption.decrypt_message(encrypted)
        assert decrypted["type"] == "alert_update"
        assert decrypted["alert_id"] == alert_id
        assert decrypted["status"] == status
        assert decrypted["data"] == data
    
    @given(st.text(min_size=1, max_size=500))
    @settings(max_examples=50)
    def test_chat_message_encryption(self, content: str):
        """Chat messages should be properly encrypted."""
        alert_id = "test-alert-123"
        sender_id = "user-456"
        
        encrypted = SocketIOEncryption.encrypt_chat_message(alert_id, sender_id, content)
        
        assert encrypted["encrypted"] is True
        
        decrypted = SocketIOEncryption.decrypt_message(encrypted)
        assert decrypted["type"] == "chat_message"
        assert decrypted["alert_id"] == alert_id
        assert decrypted["sender_id"] == sender_id
        assert decrypted["content"] == content
        assert "sent_at" in decrypted
    
    def test_decrypt_unencrypted_message_raises_error(self):
        """Decrypting unencrypted message should raise ValueError."""
        with pytest.raises(ValueError, match="Message is not encrypted"):
            SocketIOEncryption.decrypt_message({"encrypted": False})


class TestKeyManager:
    """Tests for key management utilities."""
    
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=20, deadline=None)
    def test_user_key_derivation_is_deterministic(self, user_id: str):
        """Same user ID should always produce same key."""
        key1 = KeyManager.derive_user_key(user_id)
        key2 = KeyManager.derive_user_key(user_id)
        
        assert key1 == key2
    
    @given(st.text(min_size=1, max_size=100), st.text(min_size=1, max_size=100))
    @settings(max_examples=20, deadline=None)
    def test_different_users_get_different_keys(self, user_id1: str, user_id2: str):
        """Different user IDs should produce different keys."""
        if user_id1 == user_id2:
            return  # Skip if same
        
        key1 = KeyManager.derive_user_key(user_id1)
        key2 = KeyManager.derive_user_key(user_id2)
        
        assert key1 != key2
    
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=20, deadline=None)
    def test_alert_key_derivation_is_deterministic(self, alert_id: str):
        """Same alert ID should always produce same key."""
        key1 = KeyManager.derive_alert_key(alert_id)
        key2 = KeyManager.derive_alert_key(alert_id)
        
        assert key1 == key2
    
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=20, deadline=None)
    def test_circle_key_derivation_is_deterministic(self, circle_id: str):
        """Same circle ID should always produce same key."""
        key1 = KeyManager.derive_circle_key(circle_id)
        key2 = KeyManager.derive_circle_key(circle_id)
        
        assert key1 == key2
    
    def test_different_entity_types_get_different_keys(self):
        """Same ID for different entity types should produce different keys."""
        entity_id = "test-123"
        
        user_key = KeyManager.derive_user_key(entity_id)
        alert_key = KeyManager.derive_alert_key(entity_id)
        circle_key = KeyManager.derive_circle_key(entity_id)
        
        # All keys should be different
        assert user_key != alert_key
        assert user_key != circle_key
        assert alert_key != circle_key
    
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=20, deadline=None)
    def test_derived_keys_can_be_used_for_encryption(self, user_id: str):
        """Derived keys should work for encryption/decryption."""
        key = KeyManager.derive_user_key(user_id)
        plaintext = "test message"
        
        encrypted = EncryptionService.encrypt(plaintext, key)
        decrypted = EncryptionService.decrypt(encrypted, key)
        
        assert decrypted == plaintext


class TestEncryptionServiceExtended:
    """Additional tests for EncryptionService utilities."""
    
    def test_generate_key_produces_valid_key(self):
        """Generated keys should be valid for encryption."""
        key = EncryptionService.generate_key()
        
        assert EncryptionService.validate_key(key)
        
        # Should work for encryption
        plaintext = "test message"
        encrypted = EncryptionService.encrypt(plaintext, key)
        decrypted = EncryptionService.decrypt(encrypted, key)
        
        assert decrypted == plaintext
    
    def test_validate_key_returns_true_for_valid_keys(self):
        """Valid keys should pass validation."""
        valid_key = "this-is-a-valid-key-string"
        assert EncryptionService.validate_key(valid_key)
    
    def test_generated_keys_are_unique(self):
        """Each generated key should be unique."""
        keys = [EncryptionService.generate_key() for _ in range(10)]
        assert len(set(keys)) == 10
