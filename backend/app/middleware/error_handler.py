"""Comprehensive error handling middleware.

Requirements: 9.5 - Consistent error handling with standardized error responses
Requirements: 10.5 - Return consistent JSON responses with success, message, and code fields
"""
import logging
import traceback
from typing import Any, Dict, Optional
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class ErrorResponse:
    """
    Standardized error response format.
    
    Requirements: 10.5 - Consistent JSON responses with success, message, and code fields
    """
    
    def __init__(
        self,
        success: bool = False,
        message: str = "An error occurred",
        code: str = "ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.success = success
        self.message = message
        self.code = code
        self.details = details
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        response = {
            "success": self.success,
            "message": self.message,
            "code": self.code,
        }
        if self.details:
            response["details"] = self.details
        return response


# Error code mappings
ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMIT_EXCEEDED",
    500: "INTERNAL_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
}

# User-friendly error messages
ERROR_MESSAGES = {
    400: "Invalid request",
    401: "Authentication required",
    403: "Access denied",
    404: "Resource not found",
    405: "Method not allowed",
    409: "Resource conflict",
    422: "Invalid input data",
    429: "Too many requests",
    500: "Internal server error",
    502: "Service temporarily unavailable",
    503: "Service unavailable",
}


def create_error_response(
    status_code: int,
    message: Optional[str] = None,
    code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    log_error: bool = True
) -> JSONResponse:
    """
    Create a standardized error response.
    
    Requirements: 10.5 - Consistent JSON responses
    """
    error_message = message or ERROR_MESSAGES.get(status_code, "An error occurred")
    error_code = code or ERROR_CODES.get(status_code, "ERROR")
    
    error = ErrorResponse(
        success=False,
        message=error_message,
        code=error_code,
        details=details
    )
    
    if log_error:
        logger.error(f"Error response: {status_code} - {error_code} - {error_message}")
    
    return JSONResponse(
        status_code=status_code,
        content=error.to_dict()
    )


async def http_exception_handler(
    request: Request,
    exc: HTTPException
) -> JSONResponse:
    """
    Handle FastAPI HTTPException with consistent format.
    
    Requirements: 9.5 - Consistent error handling
    """
    # Check if detail is already in our format
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.detail
        )
    
    message = str(exc.detail) if exc.detail else ERROR_MESSAGES.get(exc.status_code)
    
    return create_error_response(
        status_code=exc.status_code,
        message=message,
        log_error=exc.status_code >= 500
    )


async def starlette_exception_handler(
    request: Request,
    exc: StarletteHTTPException
) -> JSONResponse:
    """
    Handle Starlette HTTPException with consistent format.
    
    Requirements: 9.5 - Consistent error handling
    """
    return create_error_response(
        status_code=exc.status_code,
        message=str(exc.detail) if exc.detail else None,
        log_error=exc.status_code >= 500
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors with consistent format.
    
    Requirements: 9.4 - Validate all user inputs
    Requirements: 10.5 - Consistent JSON responses
    """
    # Extract validation error details
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(f"Validation error: {errors}")
    
    return create_error_response(
        status_code=422,
        message="Invalid input data",
        code="VALIDATION_ERROR",
        details={"errors": errors},
        log_error=False
    )


async def pydantic_validation_handler(
    request: Request,
    exc: ValidationError
) -> JSONResponse:
    """
    Handle Pydantic ValidationError with consistent format.
    
    Requirements: 9.4 - Validate all user inputs
    """
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field,
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(f"Pydantic validation error: {errors}")
    
    return create_error_response(
        status_code=422,
        message="Invalid input data",
        code="VALIDATION_ERROR",
        details={"errors": errors},
        log_error=False
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handle all unhandled exceptions with consistent format.
    
    Requirements: 9.5 - Consistent error handling
    """
    # Log the full traceback for debugging
    logger.error(f"Unhandled exception: {type(exc).__name__}: {str(exc)}")
    logger.error(traceback.format_exc())
    
    # Return generic error to client (don't expose internal details)
    return create_error_response(
        status_code=500,
        message="Internal server error",
        code="INTERNAL_ERROR",
        log_error=True
    )


def setup_exception_handlers(app):
    """
    Set up all exception handlers for the FastAPI app.
    
    Requirements: 9.5 - Consistent error handling
    """
    from fastapi import FastAPI
    from fastapi.exceptions import RequestValidationError
    from pydantic import ValidationError
    
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_handler)
    app.add_exception_handler(Exception, generic_exception_handler)


class AppError(Exception):
    """
    Custom application error with standardized format.
    
    Requirements: 9.5 - Consistent error handling
    """
    
    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(message)
    
    def to_response(self) -> JSONResponse:
        """Convert to JSONResponse."""
        return create_error_response(
            status_code=self.status_code,
            message=self.message,
            code=self.code,
            details=self.details
        )


class ValidationError(AppError):
    """Validation error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details=details
        )


class AuthenticationError(AppError):
    """Authentication error."""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            code="AUTH_REQUIRED",
            status_code=401
        )


class AuthorizationError(AppError):
    """Authorization error."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            code="ACCESS_DENIED",
            status_code=403
        )


class NotFoundError(AppError):
    """Resource not found error."""
    
    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=404
        )


class ConflictError(AppError):
    """Resource conflict error."""
    
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=409
        )


class RateLimitError(AppError):
    """Rate limit exceeded error."""
    
    def __init__(self, message: str = "Too many requests"):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429
        )
