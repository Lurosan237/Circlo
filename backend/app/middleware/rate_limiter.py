from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from ..core.config import get_settings

settings = get_settings()


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent abuse.
    
    Requirements: 1.4 - Rate limiting to prevent brute force attacks
    Requirements: 10.4 - Rate limiting to prevent abuse
    """
    
    def __init__(self, app):
        super().__init__(app)
        # General request tracking
        self.request_counts: dict[str, list[datetime]] = defaultdict(list)
        self.max_requests = settings.rate_limit_requests
        self.window_minutes = settings.rate_limit_window_minutes
        
        # Auth-specific rate limiting (stricter for security)
        self.auth_request_counts: dict[str, list[datetime]] = defaultdict(list)
        self.auth_max_requests = 10  # Max 10 auth attempts per window
        self.auth_window_minutes = 15  # 15 minute window for auth
    
    def _is_auth_endpoint(self, path: str) -> bool:
        """Check if the path is an authentication endpoint."""
        auth_paths = [
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/law-enforcement/login",
            "/api/v1/law-enforcement/register",
        ]
        return any(path.startswith(p) for p in auth_paths)
    
    def _clean_old_requests(
        self,
        request_dict: dict[str, list[datetime]],
        key: str,
        window_minutes: int
    ) -> list[datetime]:
        """Clean old requests outside the window."""
        now = datetime.now()
        window_start = now - timedelta(minutes=window_minutes)
        request_dict[key] = [
            req_time for req_time in request_dict[key]
            if req_time > window_start
        ]
        return request_dict[key]
    
    async def dispatch(self, request: Request, call_next):
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        
        # Skip rate limiting for health check
        if path == "/health" or path == "/api/v1/health":
            return await call_next(request)
        
        now = datetime.now()
        
        # Check auth-specific rate limit first (stricter)
        if self._is_auth_endpoint(path):
            auth_requests = self._clean_old_requests(
                self.auth_request_counts,
                client_ip,
                self.auth_window_minutes
            )
            
            if len(auth_requests) >= self.auth_max_requests:
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "message": "Too many requests",
                        "code": "RATE_LIMIT_EXCEEDED",
                    },
                )
            
            # Record auth request
            self.auth_request_counts[client_ip].append(now)
        
        # Check general rate limit
        general_requests = self._clean_old_requests(
            self.request_counts,
            client_ip,
            self.window_minutes
        )
        
        if len(general_requests) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "message": "Too many requests",
                    "code": "RATE_LIMIT_EXCEEDED",
                },
            )
        
        # Record this request
        self.request_counts[client_ip].append(now)
        
        return await call_next(request)
    
    def get_remaining_requests(self, client_ip: str) -> int:
        """Get remaining requests for a client IP."""
        self._clean_old_requests(
            self.request_counts,
            client_ip,
            self.window_minutes
        )
        return max(0, self.max_requests - len(self.request_counts[client_ip]))
    
    def get_remaining_auth_requests(self, client_ip: str) -> int:
        """Get remaining auth requests for a client IP."""
        self._clean_old_requests(
            self.auth_request_counts,
            client_ip,
            self.auth_window_minutes
        )
        return max(0, self.auth_max_requests - len(self.auth_request_counts[client_ip]))
    
    def reset_rate_limit(self, client_ip: str) -> None:
        """Reset rate limit for a client IP (for testing)."""
        self.request_counts[client_ip] = []
        self.auth_request_counts[client_ip] = []
