"""Authentication schemas for request/response validation."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserRegisterRequest(BaseModel):
    """Request schema for user registration."""
    phone_hash: str = Field(..., min_length=64, max_length=64, description="SHA-256 hash of phone number")
    name_encrypted: str = Field(..., min_length=1, description="Encrypted user name")
    password: str = Field(..., min_length=8, description="User password")


class UserLoginRequest(BaseModel):
    """Request schema for user login."""
    phone_hash: str = Field(..., min_length=64, max_length=64, description="SHA-256 hash of phone number")
    password: str = Field(..., min_length=1, description="User password")


class TokenResponse(BaseModel):
    """Response schema for authentication tokens."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token expiry in seconds")


class AuthResponse(BaseModel):
    """Standard authentication response."""
    success: bool
    message: str
    code: str
    data: Optional[TokenResponse] = None


class UserResponse(BaseModel):
    """Response schema for user data."""
    id: str
    phone_hash: str
    name_encrypted: str
    created_at: datetime
    last_active: datetime
    
    class Config:
        from_attributes = True
