"""Location service for check request processing and geofence management.

Requirements:
- 4.2: Send targeted check requests when near known routes
- 4.4: Include relevant location context without revealing exact routes
- 4.5: Never store or transmit persistent location data

IMPORTANT: This service intentionally does NOT store any route data.
Route data is stored only on the client device.
"""
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ..models.alert import Alert, AlertStatus
from ..models.circle import Circle, CircleMember, CircleType, MemberStatus


# In-memory storage for check requests and geofences
# In production, these would be stored in a database table
# but WITHOUT any route data
_check_requests: dict = {}
_geofences: dict = {}


class CheckRequest:
    """Check request model (in-memory for now)."""
    def __init__(
        self,
        id: str,
        alert_id: str,
        requester_id: str,
        general_area: str,
        description: str,
        is_near_common_location: bool = False,
        nearby_landmark: Optional[str] = None,
        is_near_known_route: bool = False,
    ):
        self.id = id
        self.alert_id = alert_id
        self.requester_id = requester_id
        self.general_area = general_area
        self.description = description
        self.is_near_common_location = is_near_common_location
        self.nearby_landmark = nearby_landmark
        self.is_near_known_route = is_near_known_route
        self.created_at = datetime.now(timezone.utc)
        self.responded_at: Optional[datetime] = None
        self.person_found: Optional[bool] = None
        self.response_notes: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'alert_id': self.alert_id,
            'requester_id': self.requester_id,
            'general_area': self.general_area,
            'description': self.description,
            'is_near_common_location': self.is_near_common_location,
            'nearby_landmark': self.nearby_landmark,
            'is_near_known_route': self.is_near_known_route,
            'created_at': self.created_at.isoformat(),
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
            'person_found': self.person_found,
        }


class Geofence:
    """Geofence model (in-memory for now)."""
    def __init__(
        self,
        id: str,
        alert_id: str,
        name: str,
        latitude: float,
        longitude: float,
        radius_meters: float = 500,
    ):
        self.id = id
        self.alert_id = alert_id
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.radius_meters = radius_meters
        self.is_active = True
        self.created_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'alert_id': self.alert_id,
            'name': self.name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'radius_meters': self.radius_meters,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
        }


class LocationService:
    """Service for location-aware check requests and geofences.
    
    IMPORTANT: This service does NOT store or process route data.
    Route data remains on the client device only.
    """
    
    # Forbidden fields that should never be in requests
    FORBIDDEN_ROUTE_FIELDS = [
        'route_points',
        'routePoints',
        'route_data',
        'routeData',
        'exact_coordinates',
        'exactCoordinates',
        'stored_routes',
        'storedRoutes',
        'route_id',
        'routeId',
    ]
    
    @staticmethod
    def validate_no_route_data(data: dict) -> Tuple[bool, str]:
        """
        Validate that no route data is present in the request.
        
        Requirements: 4.1, 4.5 - Never store or transmit route data
        
        Returns (is_valid, error_message).
        """
        for field in LocationService.FORBIDDEN_ROUTE_FIELDS:
            if field in data:
                return False, f"Route data field '{field}' is not allowed"
        
        # Recursively check nested objects
        for key, value in data.items():
            if isinstance(value, dict):
                is_valid, error = LocationService.validate_no_route_data(value)
                if not is_valid:
                    return False, error
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        is_valid, error = LocationService.validate_no_route_data(item)
                        if not is_valid:
                            return False, error
        
        return True, ""
    
    @staticmethod
    async def create_check_request(
        db: AsyncSession,
        alert_id: str,
        requester_id: UUID,
        general_area: str,
        description: str,
        is_near_common_location: bool = False,
        nearby_landmark: Optional[str] = None,
        is_near_known_route: bool = False,
    ) -> Tuple[Optional[CheckRequest], str]:
        """
        Create a check request for an alert.
        
        Requirements: 4.2 - Send targeted check requests
        Requirements: 4.4 - Location context without revealing exact routes
        
        Returns (check_request, error_message).
        """
        # Verify alert exists and is active
        try:
            alert_uuid = UUID(alert_id)
        except ValueError:
            return None, "Invalid alert ID format"
        
        result = await db.execute(
            select(Alert).where(Alert.id == alert_uuid)
        )
        alert = result.scalar_one_or_none()
        
        if not alert:
            return None, "Alert not found"
        
        if alert.status == AlertStatus.resolved:
            return None, "Cannot create check request for resolved alert"
        
        # Verify requester has access to the alert
        has_access = await LocationService._has_alert_access(
            db, alert, requester_id
        )
        if not has_access:
            return None, "Access denied to this alert"
        
        # Create check request (no route data stored)
        check_request = CheckRequest(
            id=str(uuid4()),
            alert_id=alert_id,
            requester_id=str(requester_id),
            general_area=general_area,
            description=description,
            is_near_common_location=is_near_common_location,
            nearby_landmark=nearby_landmark,
            is_near_known_route=is_near_known_route,
        )
        
        # Store in memory (in production, use database)
        _check_requests[check_request.id] = check_request
        
        return check_request, ""
    
    @staticmethod
    async def get_check_requests(
        db: AsyncSession,
        alert_id: str,
        user_id: UUID,
    ) -> List[CheckRequest]:
        """Get check requests for an alert."""
        # Filter check requests by alert_id
        return [
            cr for cr in _check_requests.values()
            if cr.alert_id == alert_id
        ]
    
    @staticmethod
    async def get_check_request(
        check_request_id: str,
    ) -> Optional[CheckRequest]:
        """Get a specific check request."""
        return _check_requests.get(check_request_id)
    
    @staticmethod
    async def respond_to_check_request(
        check_request_id: str,
        responder_id: UUID,
        person_found: bool,
        notes: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Respond to a check request.
        
        Returns (success, error_message).
        """
        check_request = _check_requests.get(check_request_id)
        if not check_request:
            return False, "Check request not found"
        
        if check_request.responded_at:
            return False, "Check request already responded to"
        
        check_request.responded_at = datetime.now(timezone.utc)
        check_request.person_found = person_found
        check_request.response_notes = notes
        
        return True, ""
    
    @staticmethod
    async def create_geofence(
        db: AsyncSession,
        alert_id: str,
        creator_id: UUID,
        name: str,
        latitude: float,
        longitude: float,
        radius_meters: float = 500,
    ) -> Tuple[Optional[Geofence], str]:
        """
        Create a geofence for targeted notifications.
        
        Requirements: 4.3 - Create geofences around common locations
        
        Returns (geofence, error_message).
        """
        # Verify alert exists
        try:
            alert_uuid = UUID(alert_id)
        except ValueError:
            return None, "Invalid alert ID format"
        
        result = await db.execute(
            select(Alert).where(Alert.id == alert_uuid)
        )
        alert = result.scalar_one_or_none()
        
        if not alert:
            return None, "Alert not found"
        
        if alert.status == AlertStatus.resolved:
            return None, "Cannot create geofence for resolved alert"
        
        # Verify creator has access
        has_access = await LocationService._has_alert_access(
            db, alert, creator_id
        )
        if not has_access:
            return None, "Access denied to this alert"
        
        # Create geofence
        geofence = Geofence(
            id=str(uuid4()),
            alert_id=alert_id,
            name=name,
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
        )
        
        # Store in memory (in production, use database)
        _geofences[geofence.id] = geofence
        
        return geofence, ""
    
    @staticmethod
    async def get_geofences(
        alert_id: str,
    ) -> List[Geofence]:
        """Get active geofences for an alert."""
        return [
            gf for gf in _geofences.values()
            if gf.alert_id == alert_id and gf.is_active
        ]
    
    @staticmethod
    async def deactivate_geofence(
        geofence_id: str,
    ) -> Tuple[bool, str]:
        """Deactivate a geofence."""
        geofence = _geofences.get(geofence_id)
        if not geofence:
            return False, "Geofence not found"
        
        geofence.is_active = False
        return True, ""
    
    @staticmethod
    async def cleanup_alert_location_data(alert_id: str) -> None:
        """
        Clean up location data when an alert is resolved.
        
        Note: This only cleans up server-side data.
        Client-side route data is managed by the client.
        """
        # Remove check requests for this alert
        to_remove = [
            cr_id for cr_id, cr in _check_requests.items()
            if cr.alert_id == alert_id
        ]
        for cr_id in to_remove:
            del _check_requests[cr_id]
        
        # Deactivate geofences for this alert
        for gf in _geofences.values():
            if gf.alert_id == alert_id:
                gf.is_active = False
    
    @staticmethod
    async def _has_alert_access(
        db: AsyncSession,
        alert: Alert,
        user_id: UUID,
    ) -> bool:
        """Check if user has access to an alert."""
        # Owner always has access
        if alert.user_id == user_id:
            return True
        
        # Check circle membership based on escalation level
        circle_types = [CircleType.inner]
        if alert.escalation_level >= 2:
            circle_types.append(CircleType.community)
        if alert.escalation_level >= 3:
            circle_types.append(CircleType.professional)
        
        result = await db.execute(
            select(CircleMember.id)
            .join(Circle, CircleMember.circle_id == Circle.id)
            .where(
                and_(
                    Circle.owner_id == alert.user_id,
                    Circle.type.in_(circle_types),
                    CircleMember.user_id == user_id,
                    CircleMember.status == MemberStatus.active
                )
            )
        )
        
        return result.scalar_one_or_none() is not None
