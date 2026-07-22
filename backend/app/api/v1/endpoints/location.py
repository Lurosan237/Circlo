"""Location API endpoints for check requests and geofences.

Requirements:
- 4.2: Send targeted check requests when near known routes
- 4.4: Include relevant location context without revealing exact routes
- 4.5: Never store or transmit persistent location data
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.database import get_db
from ....middleware.auth import get_current_user
from ....models.user import User
from ....services.location_service import LocationService
from ....schemas.location import (
    CheckRequestCreate,
    CheckRequestRespondRequest,
    CheckRequestListResponse,
    CheckRequestDetailResponse,
    CheckRequestResponse,
    GeofenceCreate,
    GeofenceListResponse,
    GeofenceDetailResponse,
    GeofenceResponse,
)

router = APIRouter()


@router.post("/check-requests", response_model=CheckRequestDetailResponse)
async def create_check_request(
    request: CheckRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a check request for an alert.
    
    Requirements: 4.2 - Send targeted check requests
    Requirements: 4.4 - Location context without revealing exact routes
    Requirements: 4.5 - Never store or transmit persistent location data
    
    IMPORTANT: This endpoint validates that no route data is included in the request.
    """
    # Validate no route data in request
    request_data = request.model_dump()
    is_valid, error = LocationService.validate_no_route_data(request_data)
    if not is_valid:
        return CheckRequestDetailResponse(
            success=False,
            message=f"Security violation: {error}",
            code="ROUTE_DATA_NOT_ALLOWED",
            data=None,
        )
    
    check_request, error = await LocationService.create_check_request(
        db=db,
        alert_id=request.alert_id,
        requester_id=current_user.id,
        general_area=request.general_area,
        description=request.description,
        is_near_common_location=request.is_near_common_location,
        nearby_landmark=request.nearby_landmark,
        is_near_known_route=request.is_near_known_route,
    )
    
    if error:
        return CheckRequestDetailResponse(
            success=False,
            message=error,
            code="CHECK_REQUEST_FAILED",
            data=None,
        )
    
    return CheckRequestDetailResponse(
        success=True,
        message="Check request created successfully",
        code="CHECK_REQUEST_CREATED",
        data=CheckRequestResponse(**check_request.to_dict()),
    )


@router.get("/check-requests", response_model=CheckRequestListResponse)
async def get_check_requests(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get check requests for an alert."""
    check_requests = await LocationService.get_check_requests(
        db=db,
        alert_id=alert_id,
        user_id=current_user.id,
    )
    
    return CheckRequestListResponse(
        success=True,
        message="Check requests retrieved successfully",
        code="CHECK_REQUESTS_RETRIEVED",
        data=[CheckRequestResponse(**cr.to_dict()) for cr in check_requests],
    )


@router.post("/check-requests/{check_request_id}/respond", response_model=CheckRequestDetailResponse)
async def respond_to_check_request(
    check_request_id: str,
    request: CheckRequestRespondRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Respond to a check request."""
    success, error = await LocationService.respond_to_check_request(
        check_request_id=check_request_id,
        responder_id=current_user.id,
        person_found=request.person_found,
        notes=request.notes,
    )
    
    if not success:
        return CheckRequestDetailResponse(
            success=False,
            message=error,
            code="RESPONSE_FAILED",
            data=None,
        )
    
    check_request = await LocationService.get_check_request(check_request_id)
    
    return CheckRequestDetailResponse(
        success=True,
        message="Response recorded successfully",
        code="RESPONSE_RECORDED",
        data=CheckRequestResponse(**check_request.to_dict()) if check_request else None,
    )


@router.post("/geofences", response_model=GeofenceDetailResponse)
async def create_geofence(
    request: GeofenceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a geofence for targeted notifications.
    
    Requirements: 4.3 - Create geofences around common locations
    """
    geofence, error = await LocationService.create_geofence(
        db=db,
        alert_id=request.alert_id,
        creator_id=current_user.id,
        name=request.name,
        latitude=request.latitude,
        longitude=request.longitude,
        radius_meters=request.radius_meters,
    )
    
    if error:
        return GeofenceDetailResponse(
            success=False,
            message=error,
            code="GEOFENCE_CREATION_FAILED",
            data=None,
        )
    
    return GeofenceDetailResponse(
        success=True,
        message="Geofence created successfully",
        code="GEOFENCE_CREATED",
        data=GeofenceResponse(**geofence.to_dict()),
    )


@router.get("/geofences", response_model=GeofenceListResponse)
async def get_geofences(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get active geofences for an alert."""
    geofences = await LocationService.get_geofences(alert_id=alert_id)
    
    return GeofenceListResponse(
        success=True,
        message="Geofences retrieved successfully",
        code="GEOFENCES_RETRIEVED",
        data=[GeofenceResponse(**gf.to_dict()) for gf in geofences],
    )


@router.delete("/geofences/{geofence_id}", response_model=GeofenceDetailResponse)
async def deactivate_geofence(
    geofence_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a geofence."""
    success, error = await LocationService.deactivate_geofence(geofence_id)
    
    if not success:
        return GeofenceDetailResponse(
            success=False,
            message=error,
            code="DEACTIVATION_FAILED",
            data=None,
        )
    
    return GeofenceDetailResponse(
        success=True,
        message="Geofence deactivated successfully",
        code="GEOFENCE_DEACTIVATED",
        data=None,
    )
