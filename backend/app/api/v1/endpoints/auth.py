"""Authentication API endpoints."""
import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from ....core.database import get_db
from ....schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    AuthResponse,
    TokenResponse,
)
from ....services.auth_service import AuthService
from ....middleware.auth import get_current_user
from ....models.user import User

router = APIRouter()

# Regex pattern for valid SHA-256 hash
SHA256_PATTERN = re.compile(r'^[a-f0-9]{64}$')


def validate_phone_hash(phone_hash: str) -> bool:
    """Validate that phone_hash is a valid SHA-256 hash."""
    return bool(SHA256_PATTERN.match(phone_hash))


@router.post("/register", response_model=AuthResponse)
async def register(
    request: UserRegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user.
    
    The phone number should be hashed client-side using SHA-256 before sending.
    This ensures the server never sees the actual phone number.
    
    Requirements: 1.1 - Phone number hashing before transmission
    """
    # Validate phone_hash format
    if not validate_phone_hash(request.phone_hash):
        return AuthResponse(
            success=False,
            message="Invalid phone hash format",
            code="VALIDATION_ERROR",
        )
    
    # Validate password length
    if len(request.password) < 8:
        return AuthResponse(
            success=False,
            message="Password must be at least 8 characters",
            code="VALIDATION_ERROR",
        )
    
    try:
        # Create user
        user = await AuthService.create_user(
            db=db,
            phone_hash=request.phone_hash,
            name_encrypted=request.name_encrypted,
            password=request.password,
        )
        
        # Generate token
        token_data = AuthService.create_user_token(user)
        
        return AuthResponse(
            success=True,
            message="User registered successfully",
            code="REGISTER_SUCCESS",
            data=TokenResponse(**token_data),
        )
    except IntegrityError:
        await db.rollback()
        # Return generic error for security - don't reveal user exists
        # Requirements: 1.3 - Consistent error responses
        return AuthResponse(
            success=False,
            message="Registration failed",
            code="REGISTER_FAILED",
        )


@router.post("/login", response_model=AuthResponse)
async def login(
    request: UserLoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user and return JWT token.
    
    Requirements: 1.2 - JWT token with 24-hour expiry
    Requirements: 1.3 - Consistent error responses without revealing user existence
    """
    # Validate phone_hash format
    if not validate_phone_hash(request.phone_hash):
        # Return same error as invalid credentials for security
        return AuthResponse(
            success=False,
            message="Invalid credentials",
            code="AUTH_FAILED",
        )
    
    # Authenticate user
    user = await AuthService.authenticate_user(
        db=db,
        phone_hash=request.phone_hash,
        password=request.password,
    )
    
    if not user:
        # Return consistent error - don't reveal if user exists or password wrong
        # Requirements: 1.3 - Consistent error responses
        return AuthResponse(
            success=False,
            message="Invalid credentials",
            code="AUTH_FAILED",
        )
    
    # Generate token with 24-hour expiry
    # Requirements: 1.2 - JWT token with 24-hour expiry
    token_data = AuthService.create_user_token(user)
    
    return AuthResponse(
        success=True,
        message="Login successful",
        code="LOGIN_SUCCESS",
        data=TokenResponse(**token_data),
    )


@router.post("/logout", response_model=AuthResponse)
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Logout user (client should discard token).
    
    Note: JWT tokens are stateless, so logout is handled client-side.
    This endpoint exists for API completeness and audit logging.
    """
    return AuthResponse(
        success=True,
        message="Logout successful",
        code="LOGOUT_SUCCESS",
    )


@router.get("/me", response_model=AuthResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information.
    
    Requirements: 1.5 - Token validation
    """
    return AuthResponse(
        success=True,
        message="User retrieved successfully",
        code="USER_RETRIEVED",
        data={
            "id": str(current_user.id),
            "phone_hash": current_user.phone_hash,
            "name_encrypted": current_user.name_encrypted,
            "created_at": current_user.created_at.isoformat(),
            "last_active": current_user.last_active.isoformat(),
        },
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    current_user: User = Depends(get_current_user)
):
    """
    Refresh JWT token for authenticated user.
    
    Requirements: 1.2 - JWT token with 24-hour expiry
    """
    token_data = AuthService.create_user_token(current_user)
    
    return AuthResponse(
        success=True,
        message="Token refreshed successfully",
        code="TOKEN_REFRESHED",
        data=TokenResponse(**token_data),
    )
