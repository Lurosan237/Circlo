"""Security headers middleware for production hardening.

Requirements: 7.1, 10.4
- Add security headers to all responses
- Implement HSTS, X-Content-Type-Options, X-Frame-Options, X-XSS-Protection
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from ..core.config import get_settings

settings = get_settings()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses.
    
    Implements security best practices for HTTP headers:
    - Strict-Transport-Security (HSTS)
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Content-Security-Policy
    - Referrer-Policy
    - Permissions-Policy
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
        # Add security headers
        self._add_security_headers(response)
        
        return response
    
    def _add_security_headers(self, response: Response) -> None:
        """Add security headers to the response."""
        
        # Strict-Transport-Security (HSTS)
        # Forces browsers to use HTTPS for all future requests
        if settings.security_hsts_enabled:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={settings.security_hsts_max_age}; includeSubDomains; preload"
            )
        
        # X-Content-Type-Options
        # Prevents MIME type sniffing
        if settings.security_content_type_nosniff:
            response.headers["X-Content-Type-Options"] = "nosniff"
        
        # X-Frame-Options
        # Prevents clickjacking attacks
        if settings.security_frame_deny:
            response.headers["X-Frame-Options"] = "DENY"
        
        # X-XSS-Protection
        # Enables browser's XSS filter
        if settings.security_xss_protection:
            response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Content-Security-Policy
        # Restricts resource loading
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self' wss: https:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        
        # Referrer-Policy
        # Controls referrer information sent with requests
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions-Policy (formerly Feature-Policy)
        # Restricts browser features
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(self), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        )
        
        # Cache-Control for API responses
        # Prevent caching of sensitive data
        if not response.headers.get("Cache-Control"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        
        # Remove server header to hide implementation details
        if "Server" in response.headers:
            del response.headers["Server"]
