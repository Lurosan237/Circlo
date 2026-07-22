from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from .core.config import get_settings
from .core.database import init_db, close_db, check_db_health
from .core.logging_config import setup_logging, get_logger
from .api.v1.router import api_router
from .middleware.rate_limiter import RateLimiterMiddleware
from .middleware.validation import ValidationMiddleware
from .middleware.security_headers import SecurityHeadersMiddleware
from .middleware.error_handler import (
    http_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
    create_error_response,
)
from .services.socketio_server import socket_app

settings = get_settings()
logger = get_logger("circlo.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.app_name} in {settings.environment} mode")
    
    await init_db()
    logger.info("Database initialized")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    await close_db()
    logger.info("Database connections closed")


app = FastAPI(
    title=settings.app_name,
    description="Privacy-first safety application API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,  # Disable docs in production
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# Security headers middleware (should be first to apply to all responses)
# Requirements: 7.1, 10.4 - Security hardening
app.add_middleware(SecurityHeadersMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Input validation middleware
# Requirements: 9.4, 10.3 - Validate and sanitize all incoming requests
app.add_middleware(ValidationMiddleware)

# Rate limiting middleware
# Requirements: 10.4 - Rate limiting to prevent abuse
app.add_middleware(RateLimiterMiddleware)


# Exception handlers for consistent error responses
# Requirements: 9.5, 10.5 - Consistent error handling with standardized responses
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)


# Include API router
app.include_router(api_router, prefix=settings.api_v1_prefix)

# Mount Socket.io server for real-time communications
# Requirements: 5.4 - Real-time updates via Socket.io with encrypted payloads
app.mount("/ws", socket_app)


@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    db_healthy = await check_db_health()
    
    status = "healthy" if db_healthy else "degraded"
    
    return {
        "success": True,
        "message": f"Service is {status}",
        "code": "HEALTH_OK" if db_healthy else "HEALTH_DEGRADED",
        "data": {
            "status": status,
            "database": "connected" if db_healthy else "disconnected",
            "environment": settings.environment,
        }
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint for Kubernetes."""
    db_healthy = await check_db_health()
    
    if not db_healthy:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "message": "Service not ready",
                "code": "NOT_READY",
            }
        )
    
    return {
        "success": True,
        "message": "Service is ready",
        "code": "READY",
    }


@app.get("/live")
async def liveness_check():
    """Liveness check endpoint for Kubernetes."""
    return {
        "success": True,
        "message": "Service is alive",
        "code": "ALIVE",
    }
