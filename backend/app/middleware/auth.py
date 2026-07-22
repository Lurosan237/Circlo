"""Authentication middleware for protected endpoints."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.security import decode_access_token
from ..core.database import get_db
from ..services.auth_service import AuthService

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    Dependency to get current authenticated user.
    Returns consistent error for security (doesn't reveal if user exists).
    """
    token = credentials.credentials
    
    # Decode token
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "message": "Invalid or expired token",
                "code": "AUTH_TOKEN_INVALID",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "message": "Invalid or expired token",
                "code": "AUTH_TOKEN_INVALID",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await AuthService.get_user_by_id(db, user_id)
    if user is None:
        # Return same error for security - don't reveal user doesn't exist
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "message": "Invalid or expired token",
                "code": "AUTH_TOKEN_INVALID",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    Optional authentication - returns None if not authenticated.
    """
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None
