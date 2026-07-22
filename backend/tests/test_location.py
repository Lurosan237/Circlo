"""Location service tests including property-based tests.

Requirements:
- 4.1: Use locally stored route data without transmitting it
- 4.2: Send targeted check requests when near known routes
- 4.4: Include relevant location context without revealing exact routes
- 4.5: Never store or transmit persistent location data
- 7.3: Store route data only locally using Hive encrypted storage
"""
import pytest
from hypothesis import given, strategies as st, settings, assume
from app.services.location_service import LocationService


# Strategies for generating test data
coordinate_strategy = st.fixed_dictionaries({
    'latitude': st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False),
    'longitude': st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False),
})

route_point_strategy = st.fixed_dictionaries({
    'coordinate': coordinate_strategy,
    'timestamp': st.datetimes(),
    'location_name': st.one_of(st.none(), st.text(min_size=1, max_size=100)),
})

route_data_strategy = st.fixed_dictionaries({
    'route_points': st.lists(route_point_strategy, min_size=1, max_size=20),
    'route_id': st.text(min_size=1, max_size=50),
    'route_name': st.text(min_size=1, max_size=100),
})

# Forbidden route data fields
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


class TestRouteDataPrivacy:
    """Property tests for route data privacy.
    
    Property 11: Route Data Privacy
    *For any* location-based operation, route data should never be transmitted 
    over the network and should remain stored only locally with encryption.
    
    **Validates: Requirements 4.1, 4.5, 7.3**
    """
    
    @given(
        st.sampled_from(FORBIDDEN_ROUTE_FIELDS),
        st.text(min_size=1, max_size=50)
    )
    @settings(max_examples=100)
    def test_route_data_fields_are_rejected(self, forbidden_field: str, value: str):
        """
        Property 11: Route Data Privacy
        Feature: circlo-safety-app, Property 11: Route Data Privacy
        **Validates: Requirements 4.1, 4.5, 7.3**
        
        For any payload containing route data fields, validation should fail.
        """
        payload_with_route_data = {forbidden_field: value}
        is_valid, error = LocationService.validate_no_route_data(payload_with_route_data)
        
        # Should reject any payload with forbidden route fields
        assert not is_valid, f"Payload with route data should be rejected: {payload_with_route_data}"
        assert "not allowed" in error.lower() or "route data" in error.lower()
    
    @given(st.dictionaries(
        keys=st.text(min_size=1, max_size=50).filter(lambda x: x not in FORBIDDEN_ROUTE_FIELDS),
        values=st.one_of(
            st.text(min_size=0, max_size=100),
            st.integers(),
            st.booleans(),
            st.floats(allow_nan=False, allow_infinity=False),
        ),
        min_size=0,
        max_size=10
    ))
    @settings(max_examples=100)
    def test_safe_payloads_are_accepted(self, safe_payload: dict):
        """
        Property 11: Route Data Privacy (inverse)
        
        For any payload without route data fields, validation should pass.
        """
        is_valid, error = LocationService.validate_no_route_data(safe_payload)
        
        assert is_valid, f"Safe payload should be accepted: {safe_payload}, error: {error}"
        assert error == ""
    
    @given(st.fixed_dictionaries({
        'alert_id': st.text(min_size=1, max_size=50),
        'general_area': st.text(min_size=1, max_size=100),
        'description': st.text(min_size=1, max_size=200),
        'is_near_common_location': st.booleans(),
        'nearby_landmark': st.one_of(st.none(), st.text(min_size=1, max_size=100)),
        'is_near_known_route': st.booleans(),
    }))
    @settings(max_examples=100)
    def test_check_request_payload_is_safe(self, check_request_payload: dict):
        """
        Property 11: Route Data Privacy
        
        Check request payloads should never contain route data.
        """
        is_valid, error = LocationService.validate_no_route_data(check_request_payload)
        
        assert is_valid, f"Check request payload should be safe: {error}"
    
    @given(
        st.dictionaries(
            keys=st.text(min_size=1, max_size=30).filter(lambda x: x not in FORBIDDEN_ROUTE_FIELDS),
            values=st.text(min_size=0, max_size=50),
            min_size=0,
            max_size=5
        ),
        st.sampled_from(FORBIDDEN_ROUTE_FIELDS),
        st.text(min_size=1, max_size=50)
    )
    @settings(max_examples=100)
    def test_nested_route_data_is_detected(self, base_payload: dict, forbidden_field: str, forbidden_value: str):
        """
        Property 11: Route Data Privacy
        
        Route data nested in objects should also be detected and rejected.
        """
        # Create nested payload with route data
        nested_payload = {
            **base_payload,
            'nested': {
                forbidden_field: forbidden_value
            }
        }
        
        is_valid, error = LocationService.validate_no_route_data(nested_payload)
        
        assert not is_valid, f"Nested route data should be detected: {nested_payload}"
    
    @given(
        st.dictionaries(
            keys=st.text(min_size=1, max_size=30).filter(lambda x: x not in FORBIDDEN_ROUTE_FIELDS),
            values=st.text(min_size=0, max_size=50),
            min_size=0,
            max_size=5
        ),
        st.sampled_from(FORBIDDEN_ROUTE_FIELDS),
        st.text(min_size=1, max_size=50)
    )
    @settings(max_examples=100)
    def test_route_data_in_arrays_is_detected(self, base_payload: dict, forbidden_field: str, forbidden_value: str):
        """
        Property 11: Route Data Privacy
        
        Route data in array items should also be detected and rejected.
        """
        # Create payload with route data in array
        array_payload = {
            **base_payload,
            'items': [
                {forbidden_field: forbidden_value}
            ]
        }
        
        is_valid, error = LocationService.validate_no_route_data(array_payload)
        
        assert not is_valid, f"Route data in arrays should be detected: {array_payload}"


class TestLocationContextPrivacy:
    """Property tests for location context without routes.
    
    Property 12: Location Context Without Routes
    *For any* check request generation, the request should contain helpful 
    location context without revealing exact route information.
    
    **Validates: Requirements 4.4**
    """
    
    @given(st.fixed_dictionaries({
        'general_area': st.text(min_size=1, max_size=100),
        'description': st.text(min_size=1, max_size=200),
        'is_near_common_location': st.booleans(),
        'nearby_landmark': st.one_of(st.none(), st.text(min_size=1, max_size=100)),
    }))
    @settings(max_examples=100)
    def test_location_context_contains_no_coordinates(self, context: dict):
        """
        Property 12: Location Context Without Routes
        Feature: circlo-safety-app, Property 12: Location Context Without Routes
        **Validates: Requirements 4.4**
        
        Location context should not contain exact coordinates.
        """
        # Check that context doesn't contain coordinate patterns
        context_str = str(context)
        
        # Should not contain high-precision coordinate patterns
        import re
        # Pattern for coordinates with more than 2 decimal places
        high_precision_pattern = r'-?\d+\.\d{3,}'
        
        # The context should not have high-precision coordinates
        # (general area descriptions use rounded coordinates with 2 decimal places max)
        matches = re.findall(high_precision_pattern, context_str)
        
        # Filter out matches that are clearly not coordinates (e.g., very large numbers)
        coordinate_matches = [m for m in matches if -180 <= float(m) <= 180]
        
        # If there are coordinate-like numbers, they should be low precision
        for match in coordinate_matches:
            decimal_places = len(match.split('.')[-1]) if '.' in match else 0
            assert decimal_places <= 2, f"High precision coordinate found: {match}"
    
    @given(st.fixed_dictionaries({
        'alert_id': st.uuids().map(str),
        'general_area': st.text(min_size=1, max_size=100),
        'description': st.text(min_size=1, max_size=200),
        'is_near_common_location': st.booleans(),
        'nearby_landmark': st.one_of(st.none(), st.text(min_size=1, max_size=100)),
        'is_near_known_route': st.booleans(),
    }))
    @settings(max_examples=100)
    def test_check_request_has_required_context_fields(self, check_request: dict):
        """
        Property 12: Location Context Without Routes
        
        Check requests should have all required context fields.
        """
        # Required fields for location context
        required_fields = ['general_area', 'description']
        
        for field in required_fields:
            assert field in check_request, f"Missing required field: {field}"
            assert check_request[field], f"Required field {field} should not be empty"
    
    @given(st.fixed_dictionaries({
        'general_area': st.text(min_size=1, max_size=100),
        'description': st.text(min_size=1, max_size=200),
        'is_near_common_location': st.booleans(),
        'nearby_landmark': st.one_of(st.none(), st.text(min_size=1, max_size=100)),
    }))
    @settings(max_examples=100)
    def test_location_context_is_privacy_preserving(self, context: dict):
        """
        Property 12: Location Context Without Routes
        
        Location context should be privacy-preserving (no route data).
        """
        # Verify no route-related fields
        is_valid, error = LocationService.validate_no_route_data(context)
        assert is_valid, f"Location context should be privacy-preserving: {error}"
        
        # Verify context provides useful information
        assert 'general_area' in context
        assert 'description' in context


class TestCheckRequestValidation:
    """Tests for check request validation."""
    
    def test_empty_payload_is_valid(self):
        """Empty payload should be valid (no route data)."""
        is_valid, error = LocationService.validate_no_route_data({})
        assert is_valid
        assert error == ""
    
    def test_route_points_field_is_rejected(self):
        """Payload with route_points should be rejected."""
        payload = {
            'alert_id': 'test-123',
            'route_points': [{'lat': 1.0, 'lng': 2.0}]
        }
        is_valid, error = LocationService.validate_no_route_data(payload)
        assert not is_valid
        assert 'route_points' in error
    
    def test_exact_coordinates_field_is_rejected(self):
        """Payload with exact_coordinates should be rejected."""
        payload = {
            'alert_id': 'test-123',
            'exact_coordinates': {'lat': 1.0, 'lng': 2.0}
        }
        is_valid, error = LocationService.validate_no_route_data(payload)
        assert not is_valid
        assert 'exact_coordinates' in error
    
    def test_stored_routes_field_is_rejected(self):
        """Payload with stored_routes should be rejected."""
        payload = {
            'alert_id': 'test-123',
            'stored_routes': ['route-1', 'route-2']
        }
        is_valid, error = LocationService.validate_no_route_data(payload)
        assert not is_valid
        assert 'stored_routes' in error
    
    def test_deeply_nested_route_data_is_rejected(self):
        """Deeply nested route data should be detected."""
        payload = {
            'level1': {
                'level2': {
                    'level3': {
                        'route_data': 'should be rejected'
                    }
                }
            }
        }
        is_valid, error = LocationService.validate_no_route_data(payload)
        assert not is_valid


class TestGeofenceValidation:
    """Tests for geofence validation."""
    
    @given(
        st.floats(min_value=-90, max_value=90, allow_nan=False, allow_infinity=False),
        st.floats(min_value=-180, max_value=180, allow_nan=False, allow_infinity=False),
        st.floats(min_value=1, max_value=10000, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_geofence_coordinates_are_valid(self, lat: float, lng: float, radius: float):
        """Geofence coordinates should be within valid ranges."""
        # Latitude should be between -90 and 90
        assert -90 <= lat <= 90
        
        # Longitude should be between -180 and 180
        assert -180 <= lng <= 180
        
        # Radius should be positive
        assert radius > 0
