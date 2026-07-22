import hashlib
import os
import base64
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from .config import get_settings

settings = get_settings()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_phone_number(phone: str) -> str:
    """Hash phone number using SHA-256 after normalization."""
    # Normalize: keep only digits, remove leading +
    normalized = ''.join(c for c in phone if c.isdigit())
    
    # Hash using SHA-256
    return hashlib.sha256(normalized.encode()).hexdigest()


def hash_pii(data: str) -> str:
    """Hash any PII data using SHA-256."""
    return hashlib.sha256(data.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token with 24-hour expiry."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            hours=settings.jwt_access_token_expire_hours
        )
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError:
        return None


class EncryptionService:
    """AES-256-GCM encryption service for secure data handling."""
    
    @staticmethod
    def _get_key(key_string: str) -> bytes:
        """Derive a 32-byte key from the key string."""
        return hashlib.sha256(key_string.encode()).digest()
    
    @staticmethod
    def encrypt(plaintext: str, key: Optional[str] = None) -> dict:
        """Encrypt data using AES-256-GCM."""
        key_bytes = EncryptionService._get_key(key or settings.encryption_key)
        
        # Generate random IV (12 bytes for GCM)
        iv = os.urandom(12)
        
        # Create cipher and encrypt
        aesgcm = AESGCM(key_bytes)
        ciphertext = aesgcm.encrypt(iv, plaintext.encode(), None)
        
        return {
            "ciphertext": base64.b64encode(ciphertext).decode(),
            "iv": base64.b64encode(iv).decode(),
        }
    
    @staticmethod
    def decrypt(encrypted_data: dict, key: Optional[str] = None) -> str:
        """Decrypt data using AES-256-GCM."""
        key_bytes = EncryptionService._get_key(key or settings.encryption_key)
        
        ciphertext = base64.b64decode(encrypted_data["ciphertext"])
        iv = base64.b64decode(encrypted_data["iv"])
        
        aesgcm = AESGCM(key_bytes)
        plaintext = aesgcm.decrypt(iv, ciphertext, None)
        
        return plaintext.decode()
    
    @staticmethod
    def derive_key_pbkdf2(
        password: str,
        salt: bytes,
        iterations: int = 100000,
        key_length: int = 32
    ) -> bytes:
        """Derive key using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=key_length,
            salt=salt,
            iterations=iterations,
        )
        return kdf.derive(password.encode())
    
    @staticmethod
    def generate_salt() -> bytes:
        """Generate random salt for key derivation."""
        return os.urandom(32)
    
    @staticmethod
    def generate_key() -> str:
        """Generate a new random encryption key (32 bytes, base64 encoded)."""
        return base64.b64encode(os.urandom(32)).decode()
    
    @staticmethod
    def validate_key(key: str) -> bool:
        """Validate that a key is properly formatted and usable."""
        try:
            key_bytes = EncryptionService._get_key(key)
            return len(key_bytes) == 32
        except Exception:
            return False


class SocketIOEncryption:
    """Encryption utilities specifically for Socket.io message handling."""
    
    @staticmethod
    def encrypt_message(message: dict, key: Optional[str] = None) -> dict:
        """
        Encrypt a Socket.io message payload.
        
        Args:
            message: Dictionary containing the message data
            key: Optional encryption key (uses settings.encryption_key if not provided)
            
        Returns:
            Dictionary with encrypted payload ready for Socket.io transmission
        """
        import json
        
        # Serialize message to JSON string
        message_json = json.dumps(message, separators=(',', ':'))
        
        # Encrypt the serialized message
        encrypted = EncryptionService.encrypt(message_json, key)
        
        return {
            "encrypted": True,
            "payload": encrypted["ciphertext"],
            "iv": encrypted["iv"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    @staticmethod
    def decrypt_message(encrypted_message: dict, key: Optional[str] = None) -> dict:
        """
        Decrypt a Socket.io message payload.
        
        Args:
            encrypted_message: Dictionary containing encrypted payload
            key: Optional encryption key (uses settings.encryption_key if not provided)
            
        Returns:
            Original message dictionary
        """
        import json
        
        if not encrypted_message.get("encrypted", False):
            raise ValueError("Message is not encrypted")
        
        encrypted_data = {
            "ciphertext": encrypted_message["payload"],
            "iv": encrypted_message["iv"],
        }
        
        # Decrypt the payload
        decrypted_json = EncryptionService.decrypt(encrypted_data, key)
        
        # Parse JSON back to dictionary
        return json.loads(decrypted_json)
    
    @staticmethod
    def encrypt_alert_update(
        alert_id: str,
        status: str,
        data: Optional[dict] = None,
        key: Optional[str] = None
    ) -> dict:
        """
        Encrypt an alert status update for real-time transmission.
        
        Args:
            alert_id: The alert identifier
            status: Current alert status
            data: Additional alert data
            key: Optional encryption key
            
        Returns:
            Encrypted message ready for Socket.io
        """
        message = {
            "type": "alert_update",
            "alert_id": alert_id,
            "status": status,
            "data": data or {},
        }
        return SocketIOEncryption.encrypt_message(message, key)
    
    @staticmethod
    def encrypt_chat_message(
        alert_id: str,
        sender_id: str,
        content: str,
        key: Optional[str] = None
    ) -> dict:
        """
        Encrypt a chat message for an active alert.
        
        Args:
            alert_id: The alert this message belongs to
            sender_id: ID of the message sender
            content: Message content
            key: Optional encryption key
            
        Returns:
            Encrypted message ready for Socket.io
        """
        message = {
            "type": "chat_message",
            "alert_id": alert_id,
            "sender_id": sender_id,
            "content": content,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        return SocketIOEncryption.encrypt_message(message, key)


class KeyManager:
    """Secure key management utilities."""
    
    @staticmethod
    def derive_user_key(user_id: str, master_key: Optional[str] = None) -> str:
        """
        Derive a user-specific encryption key from the master key.
        
        Args:
            user_id: The user's unique identifier
            master_key: Optional master key (uses settings.encryption_key if not provided)
            
        Returns:
            Base64-encoded derived key for the user
        """
        master = master_key or settings.encryption_key
        salt = hashlib.sha256(user_id.encode()).digest()
        
        derived = EncryptionService.derive_key_pbkdf2(
            password=master,
            salt=salt,
            iterations=100000,
            key_length=32
        )
        
        return base64.b64encode(derived).decode()
    
    @staticmethod
    def derive_alert_key(alert_id: str, master_key: Optional[str] = None) -> str:
        """
        Derive an alert-specific encryption key for secure communications.
        
        Args:
            alert_id: The alert's unique identifier
            master_key: Optional master key (uses settings.encryption_key if not provided)
            
        Returns:
            Base64-encoded derived key for the alert
        """
        master = master_key or settings.encryption_key
        salt = hashlib.sha256(f"alert:{alert_id}".encode()).digest()
        
        derived = EncryptionService.derive_key_pbkdf2(
            password=master,
            salt=salt,
            iterations=100000,
            key_length=32
        )
        
        return base64.b64encode(derived).decode()
    
    @staticmethod
    def derive_circle_key(circle_id: str, master_key: Optional[str] = None) -> str:
        """
        Derive a circle-specific encryption key for group communications.
        
        Args:
            circle_id: The circle's unique identifier
            master_key: Optional master key (uses settings.encryption_key if not provided)
            
        Returns:
            Base64-encoded derived key for the circle
        """
        master = master_key or settings.encryption_key
        salt = hashlib.sha256(f"circle:{circle_id}".encode()).digest()
        
        derived = EncryptionService.derive_key_pbkdf2(
            password=master,
            salt=salt,
            iterations=100000,
            key_length=32
        )
        
        return base64.b64encode(derived).decode()
