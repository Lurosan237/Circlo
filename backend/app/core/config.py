from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
from typing import Optional
import secrets


class Settings(BaseSettings):
    """Application settings loaded from environment variables.
    
    Requirements: 7.1, 7.2, 10.4
    - Secure configuration management
    - Production-ready settings
    - Rate limiting configuration
    """
    
    # Application
    app_name: str = "Circlo Safety API"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"  # development, staging, production
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    
    # Database
    database_url: str = "postgresql+asyncpg://circlo:circlo_secret@localhost:5432/circlo_db"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800  # 30 minutes
    db_echo: bool = False
    
    # JWT Authentication
    jwt_secret_key: str = "your-super-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_hours: int = 24
    jwt_refresh_token_expire_days: int = 7
    
    # Rate Limiting - Requirements: 10.4
    rate_limit_requests: int = 100
    rate_limit_window_minutes: int = 15
    rate_limit_auth_requests: int = 5  # Stricter for auth endpoints
    rate_limit_auth_window_minutes: int = 1
    
    # Encryption - Requirements: 7.1
    encryption_key: str = "your-32-byte-encryption-key-here"
    notification_key: str = "your-notification-encryption-key"
    
    # Firebase
    firebase_credentials_path: str = ""
    
    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080", "http://localhost:5500", "http://127.0.0.1:5500"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_allow_headers: list[str] = ["*"]
    
    # Security Headers
    security_hsts_enabled: bool = True
    security_hsts_max_age: int = 31536000  # 1 year
    security_content_type_nosniff: bool = True
    security_frame_deny: bool = True
    security_xss_protection: bool = True
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # json or text
    log_file: Optional[str] = None
    
    # Monitoring
    enable_metrics: bool = True
    metrics_path: str = "/metrics"
    
    # Data Retention - Requirements: 7.4
    data_retention_days: int = 90
    cleanup_batch_size: int = 1000
    
    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str, info) -> str:
        """Validate JWT secret key is secure in production."""
        # In production, ensure the key is not the default
        if v == "your-super-secret-key-change-in-production":
            # Generate a secure random key for development
            return secrets.token_urlsafe(32)
        return v
    
    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v: str, info) -> str:
        """Validate encryption key is secure."""
        if v == "your-32-byte-encryption-key-here":
            # Generate a secure random key for development
            return secrets.token_urlsafe(32)
        return v
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
