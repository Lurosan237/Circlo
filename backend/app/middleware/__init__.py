"""Middleware package for Circlo Safety API.

This package contains middleware for:
- Authentication (auth.py)
- Rate limiting (rate_limiter.py)
- Input validation (validation.py)
- Error handling (error_handler.py)
- Law enforcement authentication (law_enforcement_auth.py)
- Security headers (security_headers.py)
"""
from .auth import get_current_user, get_current_user_optional
from .rate_limiter import RateLimiterMiddleware
from .validation import ValidationMiddleware, InputValidator, sanitize_string, sanitize_dict
from .error_handler import (
    ErrorResponse,
    create_error_response,
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
    setup_exception_handlers,
    AppError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ConflictError,
    RateLimitError,
)
from .security_headers import SecurityHeadersMiddleware

__all__ = [
    # Auth
    "get_current_user",
    "get_current_user_optional",
    # Rate limiting
    "RateLimiterMiddleware",
    # Validation
    "ValidationMiddleware",
    "InputValidator",
    "sanitize_string",
    "sanitize_dict",
    # Error handling
    "ErrorResponse",
    "create_error_response",
    "http_exception_handler",
    "validation_exception_handler",
    "generic_exception_handler",
    "setup_exception_handlers",
    "AppError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ConflictError",
    "RateLimitError",
    # Security headers
    "SecurityHeadersMiddleware",
]
