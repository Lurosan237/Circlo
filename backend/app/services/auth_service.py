"""Authentication service for user management."""
from datetime import timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.user import User
from ..core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
)
from ..core.config import get_settings

settings = get_settings()


class AuthService:
    """Service for authentication operations."""
    
    @staticmethod
    async def get_user_by_phone_hash(
        db: AsyncSession,
        phone_hash: str
    ) -> Optional[User]:
        """Get user by phone hash."""
        result = await db.execute(
            select(User).where(User.phone_hash == phone_hash)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_by_id(
        db: AsyncSession,
        user_id: str
    ) -> Optional[User]:
        """Get user by ID."""
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_user(
        db: AsyncSession,
        phone_hash: str,
        name_encrypted: str,
        password: str
    ) -> User:
        """Create a new user."""
        user = User(
            phone_hash=phone_hash,
            name_encrypted=name_encrypted,
            password_hash=get_password_hash(password),
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user
    
    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        phone_hash: str,
        password: str
    ) -> Optional[User]:
        """Authenticate user with phone hash and password."""
        user = await AuthService.get_user_by_phone_hash(db, phone_hash)
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user
    
    @staticmethod
    def create_user_token(user: User) -> dict:
        """Create JWT token for user."""
        expires_delta = timedelta(hours=settings.jwt_access_token_expire_hours)
        access_token = create_access_token(
            data={"sub": str(user.id), "phone_hash": user.phone_hash},
            expires_delta=expires_delta
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_hours * 3600,
        }
