"""Location schemas for check requests and geofences.

Requirements:
- 4.2: Send targeted check requests when near known routes
- 4.4: Include relevant location context without revealing exact routes
- 4.5: Never store or transmit persistent location data
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class CheckRequestCreate(BaseModel):
    """Schema for creating a check request.
    
    Note: This schema intentionally does NOT include route data.
    Requirements: 4.1, 4.5 - Never transmit route data
    """
    alert_id: str = Field(..., description="ID of the alert")
    general_area: str = Field(..., description="General area description (privacy-preserving)")
    description: str = Field(..., description="Location context description")
    is_near_common_location: bool = Field(default=False, description="Whether near a common location")
    nearby_landmark: Optional[str] = Field(None, description="Nearby landmark name if any")
    is_near_known_route: bool = Field(default=False, description="Whether near a known route (boolean only, no route data)")


class CheckRequestResponse(BaseModel):
    """Schema for check request response."""
    id: str
    alert_id: str
    requester_id: str
    general_area: str
    description: str
    is_near_common_location: bool
    nearby_landmark: Optional[str]
    is_near_known_route: bool
    created_at: datetime
    responded_at: Optional[datetime]
    person_found: Optional[bool]


class CheckRequestRespondRequest(BaseModel):
    """Schema for responding to a check request."""
    person_found: bool = Field(..., description="Whether the person was found")
    notes: Optional[str] = Field(None, description="Optional notes about the response")


class GeofenceCreate(BaseModel):
    """Schema for creating a geofence.
    
    Requirements: 4.3 - Create geofences around common locations
    """
    alert_id: str = Field(..., description="ID of the alert")
    name: str = Field(..., description="Name of the geofence location")
    latitude: float = Field(..., ge=-90, le=90, description="Center latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Center longitude")
    radius_meters: float = Field(default=500, gt=0, le=10000, description="Radius in meters")


class GeofenceResponse(BaseModel):
    """Schema for geofence response."""
    id: str
    alert_id: str
    name: str
    latitude: float
    longitude: float
    radius_meters: float
    is_active: bool
    created_at: datetime


class CheckRequestListResponse(BaseModel):
    """Response for list of check requests."""
    success: bool
    message: str
    code: str
    data: List[CheckRequestResponse]


class CheckRequestDetailResponse(BaseModel):
    """Response for single check request."""
    success: bool
    message: str
    code: str
    data: Optional[CheckRequestResponse]


class GeofenceListResponse(BaseModel):
    """Response for list of geofences."""
    success: bool
    message: str
    code: str
    data: List[GeofenceResponse]


class GeofenceDetailResponse(BaseModel):
    """Response for single geofence."""
    success: bool
    message: str
    code: str
    data: Optional[GeofenceResponse]


class LocationContextResponse(BaseModel):
    """Response for location context (privacy-preserving).
    
    Requirements: 4.4 - Location context without revealing exact routes
    """
    general_area: str
    description: str
    is_near_common_location: bool
    nearby_landmark: Optional[str]
