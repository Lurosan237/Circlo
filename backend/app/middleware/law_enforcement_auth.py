"""Law enforcement authentication middleware.

Requirements: 6.1 - Verify official credentials before granting access
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.security import decode_access_token
from ..core.database import get_db
from ..services.law_enforcement_service import LawEnforcementService

le_security = HTTPBearer()


async def get_current_le_officer(
    credentials: HTTPAuthorizationCredentials = Depends(le_security),
    db: AsyncSession = Depends(get_db)
):
    """
    Dependency to get current authenticated law enforcement officer.
    
    Requirements: 6.1 - Verify official credentials
    
    Returns consistent error for security (doesn't reveal if officer exists).
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
                "code": "LE_AUTH_TOKEN_INVALID",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify token type
    token_type = payload.get("type")
    if token_type != "law_enforcement":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "message": "Invalid or expired token",
                "code": "LE_AUTH_TOKEN_INVALID",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get officer from database
    officer_id = payload.get("sub")
    if not officer_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "message": "Invalid or expired token",
                "code": "LE_AUTH_TOKEN_INVALID",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    officer = await LawEnforcementService.get_officer_by_id(db, officer_id)
    if officer is None:
        # Return same error for security - don't reveal officer doesn't exist
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "message": "Invalid or expired token",
                "code": "LE_AUTH_TOKEN_INVALID",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify officer is still active and verified
    if not officer.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "message": "Account is deactivated",
                "code": "LE_ACCOUNT_DEACTIVATED",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not officer.is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "message": "Account pending verification",
                "code": "LE_ACCOUNT_PENDING",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return officer
