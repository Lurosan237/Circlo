import '../../../core/base/base_repository.dart';
import '../../../core/services/api_service.dart';
import '../../../core/services/location_service.dart';
import '../../../core/models/location.dart';

/// Repository for location-related API operations
/// 
/// Requirements:
/// - 4.1: Use locally stored route data without transmitting it
/// - 4.2: Send targeted check requests when near known routes
/// - 4.4: Include relevant location context without revealing exact routes
/// - 4.5: Never store or transmit persistent location data
class LocationRepository extends BaseRepository {
  LocationRepository({required super.apiService});

  /// Send a check request to the backend
  /// Requirements: 4.2, 4.4 - Location context without revealing exact routes
  Future<Result<CheckRequest>> sendCheckRequest({
    required String alertId,
    required GeoCoordinate currentLocation,
  }) async {
    // Generate check request locally (uses local route data)
    final checkRequest = await LocationService.generateCheckRequest(
      alertId: alertId,
      targetUserId: '', // Will be set by backend
      currentLocation: currentLocation,
    );
    
    // Create safe payload (no route data transmitted)
    final context = LocationContext(
      generalArea: checkRequest.generalArea ?? 'Unknown area',
      description: checkRequest.locationContext,
      isNearCommonLocation: checkRequest.isNearKnownRoute,
    );
    
    final payload = LocationService.createSafeNetworkPayload(
      alertId: alertId,
      context: context,
      isNearKnownRoute: checkRequest.isNearKnownRoute,
    );
    
    // Validate no route data in payload before sending
    if (!LocationService.validateNoRouteDataInPayload(payload)) {
      return Result.failure(
        'Security error: Route data detected in payload',
        code: 'ROUTE_DATA_LEAK_PREVENTED',
      );
    }
    
    final response = await apiService.post<Map<String, dynamic>>(
      '/location/check-requests',
      data: payload,
    );

    if (response.success && response.data != null) {
      final data = response.data!['data'] as Map<String, dynamic>?;
      if (data != null) {
        return Result.success(CheckRequest.fromJson(data));
      }
    }

    return Result.failure(
      response.message ?? 'Failed to send check request',
      code: response.code,
    );
  }

  /// Get check requests for an alert
  Future<Result<List<CheckRequest>>> getCheckRequests(String alertId) async {
    final response = await apiService.get<Map<String, dynamic>>(
      '/location/check-requests',
      queryParameters: {'alert_id': alertId},
    );

    if (response.success && response.data != null) {
      final dataList = response.data!['data'] as List<dynamic>?;
      if (dataList != null) {
        final requests = dataList
            .map((json) => CheckRequest.fromJson(json as Map<String, dynamic>))
            .toList();
        return Result.success(requests);
      }
      return Result.success([]);
    }

    return Result.failure(
      response.message ?? 'Failed to get check requests',
      code: response.code,
    );
  }

  /// Respond to a check request
  Future<Result<bool>> respondToCheckRequest({
    required String checkRequestId,
    required bool personFound,
    String? notes,
  }) async {
    final response = await apiService.post<Map<String, dynamic>>(
      '/location/check-requests/$checkRequestId/respond',
      data: {
        'person_found': personFound,
        if (notes != null) 'notes': notes,
      },
    );

    if (response.success) {
      return Result.success(true);
    }

    return Result.failure(
      response.message ?? 'Failed to respond to check request',
      code: response.code,
    );
  }

  /// Get geofence triggers for notifications
  /// Requirements: 4.3 - Geofences for targeted notifications
  Future<Result<List<Geofence>>> getActiveGeofences(String alertId) async {
    final response = await apiService.get<Map<String, dynamic>>(
      '/location/geofences',
      queryParameters: {'alert_id': alertId},
    );

    if (response.success && response.data != null) {
      final dataList = response.data!['data'] as List<dynamic>?;
      if (dataList != null) {
        final geofences = dataList
            .map((json) => Geofence.fromJson(json as Map<String, dynamic>))
            .toList();
        return Result.success(geofences);
      }
      return Result.success([]);
    }

    return Result.failure(
      response.message ?? 'Failed to get geofences',
      code: response.code,
    );
  }
}
