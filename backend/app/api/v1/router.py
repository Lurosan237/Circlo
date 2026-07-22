from fastapi import APIRouter
from .endpoints import auth, circles, alerts, location, messages, notifications, law_enforcement

api_router = APIRouter()

# Health check for API v1
@api_router.get("/health")
async def api_health():
    """API v1 health check."""
    return {
        "success": True,
        "message": "API v1 is healthy",
        "code": "API_HEALTH_OK",
    }

# Include authentication router
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Include circles router
api_router.include_router(circles.router, prefix="/circles", tags=["Circles"])

# Include alerts router
api_router.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])

# Include location router
api_router.include_router(location.router, prefix="/location", tags=["Location"])

# Include messages router
api_router.include_router(messages.router, prefix="/messages", tags=["Messages"])

# Include notifications router
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])

# Include law enforcement router
api_router.include_router(law_enforcement.router, prefix="/law-enforcement", tags=["Law Enforcement"])
