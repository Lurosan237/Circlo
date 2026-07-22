import 'package:freezed_annotation/freezed_annotation.dart';

part 'location.freezed.dart';
part 'location.g.dart';

/// Geographic coordinate model
@freezed
class GeoCoordinate with _$GeoCoordinate {
  const factory GeoCoordinate({
    required double latitude,
    required double longitude,
  }) = _GeoCoordinate;

  factory GeoCoordinate.fromJson(Map<String, dynamic> json) =>
      _$GeoCoordinateFromJson(json);
}

/// Route point with timestamp
@freezed
class RoutePoint with _$RoutePoint {
  const factory RoutePoint({
    required GeoCoordinate coordinate,
    required DateTime timestamp,
    String? locationName,
  }) = _RoutePoint;

  factory RoutePoint.fromJson(Map<String, dynamic> json) =>
      _$RoutePointFromJson(json);
}

/// Stored route data (never transmitted over network)
/// Requirements: 4.1, 7.3 - Route data stored locally only
@freezed
class StoredRoute with _$StoredRoute {
  const factory StoredRoute({
    required String id,
    required String name,
    required List<RoutePoint> points,
    required DateTime createdAt,
    required DateTime lastUsed,
    @Default(0) int usageCount,
  }) = _StoredRoute;

  factory StoredRoute.fromJson(Map<String, dynamic> json) =>
      _$StoredRouteFromJson(json);
}

/// Geofence definition for location-aware notifications
/// Requirements: 4.3 - Geofences around common locations
@freezed
class Geofence with _$Geofence {
  const factory Geofence({
    required String id,
    required String name,
    required GeoCoordinate center,
    required double radiusMeters,
    @Default(true) bool isActive,
  }) = _Geofence;

  factory Geofence.fromJson(Map<String, dynamic> json) =>
      _$GeofenceFromJson(json);
}

/// Check request with location context (no exact routes)
/// Requirements: 4.4 - Location context without revealing exact routes
@freezed
class CheckRequest with _$CheckRequest {
  const factory CheckRequest({
    required String id,
    required String alertId,
    required String targetUserId,
    required String locationContext,
    required DateTime createdAt,
    String? generalArea,
    @Default(false) bool isNearKnownRoute,
  }) = _CheckRequest;

  factory CheckRequest.fromJson(Map<String, dynamic> json) =>
      _$CheckRequestFromJson(json);
}

/// Location context for check requests (privacy-preserving)
/// Requirements: 4.4 - Include relevant location context without revealing exact routes
@freezed
class LocationContext with _$LocationContext {
  const factory LocationContext({
    required String generalArea,
    required String description,
    @Default(false) bool isNearCommonLocation,
    String? nearbyLandmark,
  }) = _LocationContext;

  factory LocationContext.fromJson(Map<String, dynamic> json) =>
      _$LocationContextFromJson(json);
}
