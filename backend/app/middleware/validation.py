"""Input validation middleware for all API endpoints.

Requirements: 9.4 - Validate all user inputs before processing
Requirements: 10.3 - Validate and sanitize all incoming requests
Requirements: 10.5 - Return consistent JSON responses
"""
import re
import html
import logging
from typing import Any, Dict, Optional, Callable
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import ValidationError

# Configure logging
logger = logging.getLogger(__name__)


class ValidationMiddleware(BaseHTTPMiddleware):
    """
    Middleware for input validation and sanitization.
    
    Requirements: 9.4 - Validate all user inputs before processing
    Requirements: 10.3 - Validate and sanitize all incoming requests
    """
    
    # Patterns for detecting potentially malicious input
    SQL_INJECTION_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE)\b)",
        r"(--|;|\/\*|\*\/)",
        r"(\bOR\b\s+\d+\s*=\s*\d+)",
        r"(\bAND\b\s+\d+\s*=\s*\d+)",
    ]
    
    XSS_PATTERNS = [
        r"<script[^>]*>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>",
    ]
    
    # Maximum sizes for various inputs
    MAX_STRING_LENGTH = 10000
    MAX_JSON_DEPTH = 10
    MAX_ARRAY_LENGTH = 1000
    
    def __init__(self, app):
        super().__init__(app)
        self.sql_patterns = [re.compile(p, re.IGNORECASE) for p in self.SQL_INJECTION_PATTERNS]
        self.xss_patterns = [re.compile(p, re.IGNORECASE) for p in self.XSS_PATTERNS]
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Process request through validation middleware."""
        # Skip validation for health check endpoints
        if request.url.path in ["/health", "/api/v1/health"]:
            return await call_next(request)
        
        # Validate query parameters
        query_validation = self._validate_query_params(dict(request.query_params))
        if query_validation:
            logger.warning(f"Query param validation failed: {query_validation}")
            return self._create_error_response(
                status_code=400,
                message=query_validation,
                code="VALIDATION_ERROR"
            )
        
        # Validate path parameters
        path_validation = self._validate_path(request.url.path)
        if path_validation:
            logger.warning(f"Path validation failed: {path_validation}")
            return self._create_error_response(
                status_code=400,
                message=path_validation,
                code="VALIDATION_ERROR"
            )
        
        # For POST/PUT/PATCH requests, validate body
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                # Read body for validation
                body = await request.body()
                if body:
                    import json
                    try:
                        json_body = json.loads(body)
                        body_validation = self._validate_json_body(json_body)
                        if body_validation:
                            logger.warning(f"Body validation failed: {body_validation}")
                            return self._create_error_response(
                                status_code=400,
                                message=body_validation,
                                code="VALIDATION_ERROR"
                            )
                    except json.JSONDecodeError:
                        # Not JSON, skip JSON-specific validation
                        pass
            except Exception as e:
                logger.error(f"Error reading request body: {e}")
        
        return await call_next(request)
    
    def _validate_query_params(self, params: Dict[str, Any]) -> Optional[str]:
        """Validate query parameters for malicious content."""
        for key, value in params.items():
            # Check key
            if self._contains_malicious_content(key):
                return f"Invalid query parameter name"
            
            # Check value
            if isinstance(value, str):
                if len(value) > self.MAX_STRING_LENGTH:
                    return f"Query parameter value too long"
                if self._contains_malicious_content(value):
                    return f"Invalid query parameter value"
        
        return None
    
    def _validate_path(self, path: str) -> Optional[str]:
        """Validate URL path for malicious content."""
        # Check for path traversal attempts
        if ".." in path or "~" in path:
            return "Invalid path"
        
        # Check for malicious patterns
        if self._contains_malicious_content(path):
            return "Invalid path"
        
        return None
    
    def _validate_json_body(self, body: Any, depth: int = 0) -> Optional[str]:
        """Recursively validate JSON body."""
        if depth > self.MAX_JSON_DEPTH:
            return "Request body too deeply nested"
        
        if isinstance(body, dict):
            for key, value in body.items():
                # Validate key
                if not isinstance(key, str):
                    return "Invalid JSON key type"
                if self._contains_malicious_content(key):
                    return "Invalid field name"
                
                # Recursively validate value
                result = self._validate_json_body(value, depth + 1)
                if result:
                    return result
        
        elif isinstance(body, list):
            if len(body) > self.MAX_ARRAY_LENGTH:
                return "Array too large"
            for item in body:
                result = self._validate_json_body(item, depth + 1)
                if result:
                    return result
        
        elif isinstance(body, str):
            if len(body) > self.MAX_STRING_LENGTH:
                return "String value too long"
            if self._contains_malicious_content(body):
                return "Invalid input detected"
        
        return None
    
    def _contains_malicious_content(self, value: str) -> bool:
        """Check if value contains potentially malicious content."""
        # Check SQL injection patterns
        for pattern in self.sql_patterns:
            if pattern.search(value):
                return True
        
        # Check XSS patterns
        for pattern in self.xss_patterns:
            if pattern.search(value):
                return True
        
        return False
    
    def _create_error_response(
        self,
        status_code: int,
        message: str,
        code: str
    ) -> JSONResponse:
        """Create consistent error response."""
        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "message": message,
                "code": code,
            }
        )


def sanitize_string(value: str) -> str:
    """
    Sanitize a string value by escaping HTML entities.
    
    Requirements: 10.3 - Sanitize all incoming requests
    """
    if not isinstance(value, str):
        return value
    
    # Escape HTML entities
    sanitized = html.escape(value)
    
    # Remove null bytes
    sanitized = sanitized.replace('\x00', '')
    
    return sanitized


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively sanitize all string values in a dictionary.
    
    Requirements: 10.3 - Sanitize all incoming requests
    """
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_string(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_string(item) if isinstance(item, str)
                else sanitize_dict(item) if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


class InputValidator:
    """
    Utility class for validating specific input types.
    
    Requirements: 9.4 - Validate all user inputs before processing
    """
    
    # UUID pattern
    UUID_PATTERN = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    
    # SHA-256 hash pattern
    SHA256_PATTERN = re.compile(r'^[a-f0-9]{64}$', re.IGNORECASE)
    
    # Email pattern (basic)
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    @classmethod
    def is_valid_uuid(cls, value: str) -> bool:
        """Validate UUID format."""
        if not isinstance(value, str):
            return False
        return bool(cls.UUID_PATTERN.match(value))
    
    @classmethod
    def is_valid_sha256(cls, value: str) -> bool:
        """Validate SHA-256 hash format."""
        if not isinstance(value, str):
            return False
        return bool(cls.SHA256_PATTERN.match(value))
    
    @classmethod
    def is_valid_email(cls, value: str) -> bool:
        """Validate email format."""
        if not isinstance(value, str):
            return False
        return bool(cls.EMAIL_PATTERN.match(value))
    
    @classmethod
    def validate_string_length(
        cls,
        value: str,
        min_length: int = 0,
        max_length: int = 10000
    ) -> bool:
        """Validate string length."""
        if not isinstance(value, str):
            return False
        return min_length <= len(value) <= max_length
    
    @classmethod
    def validate_integer_range(
        cls,
        value: int,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None
    ) -> bool:
        """Validate integer range."""
        if not isinstance(value, int):
            return False
        if min_value is not None and value < min_value:
            return False
        if max_value is not None and value > max_value:
            return False
        return True
