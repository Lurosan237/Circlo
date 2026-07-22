"""Production logging configuration.

Requirements: 10.5
- Implement production logging and monitoring
- Structured JSON logging for production
- Request/response logging with sensitive data redaction
"""
import logging
import sys
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from .config import get_settings

settings = get_settings()


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging in production."""
    
    # Fields to redact from logs
    SENSITIVE_FIELDS = {
        "password", "token", "secret", "key", "authorization",
        "phone", "phone_hash", "name_encrypted", "content_encrypted",
        "api_key", "access_token", "refresh_token"
    }
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, "extra"):
            extra = self._redact_sensitive(record.extra)
            log_data["extra"] = extra
        
        # Add request context if available
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        
        return json.dumps(log_data)
    
    def _redact_sensitive(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive fields from log data."""
        if not isinstance(data, dict):
            return data
        
        redacted = {}
        for key, value in data.items():
            if key.lower() in self.SENSITIVE_FIELDS:
                redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = self._redact_sensitive(value)
            else:
                redacted[key] = value
        
        return redacted


class TextFormatter(logging.Formatter):
    """Text formatter for development logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        return f"{timestamp} | {record.levelname:8} | {record.name} | {record.getMessage()}"


def setup_logging() -> None:
    """Configure logging based on environment settings."""
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Set formatter based on environment
    if settings.log_format == "json" or settings.is_production:
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Add file handler if configured
    if settings.log_file:
        file_handler = logging.FileHandler(settings.log_file)
        file_handler.setLevel(getattr(logging, settings.log_level.upper()))
        file_handler.setFormatter(JSONFormatter())  # Always use JSON for file logs
        root_logger.addHandler(file_handler)
    
    # Configure specific loggers
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if settings.debug else logging.WARNING
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name."""
    return logging.getLogger(name)


class RequestLogger:
    """Logger for HTTP requests with sensitive data redaction."""
    
    def __init__(self):
        self.logger = get_logger("circlo.requests")
    
    def log_request(
        self,
        method: str,
        path: str,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> None:
        """Log an incoming request."""
        extra = {
            "method": method,
            "path": path,
            "client_ip": client_ip,
        }
        
        record = self.logger.makeRecord(
            self.logger.name,
            logging.INFO,
            "",
            0,
            f"Request: {method} {path}",
            (),
            None,
        )
        record.extra = extra
        if request_id:
            record.request_id = request_id
        if user_id:
            record.user_id = user_id
        
        self.logger.handle(record)
    
    def log_response(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        request_id: Optional[str] = None,
    ) -> None:
        """Log a response."""
        extra = {
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
        }
        
        level = logging.INFO if status_code < 400 else logging.WARNING
        if status_code >= 500:
            level = logging.ERROR
        
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            "",
            0,
            f"Response: {method} {path} - {status_code} ({duration_ms:.2f}ms)",
            (),
            None,
        )
        record.extra = extra
        if request_id:
            record.request_id = request_id
        
        self.logger.handle(record)


# Global request logger instance
request_logger = RequestLogger()
