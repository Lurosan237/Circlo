import 'dart:convert';
import 'dart:math';
import 'package:uuid/uuid.dart';
import '../models/location.dart';
import 'secure_storage_service.dart';
import 'security_service.dart';

/// Location storage keys for Hive encrypted storage
class LocationStorageKeys {
  static const String routesPrefix = 'route_';
  static const String geofencesPrefix = 'geofence_';
  static const String routeIndex = 'route_index';
  static const String geofenceIndex = 'geofence_index';
}

/// Location service for privacy-preserving location features
/// 
/// Requirements:
/// - 4.1: Use locally stored route data without transmitting it
/// - 4.2: Send targeted check requests when near known routes
/// - 4.3: Create geofences around common locations using Mapbox SDK
/// - 4.4: Include relevant location context without revealing exact routes
/// - 4.5: Never store or transmit persistent location data
/// - 7.3: Store route data only locally using Hive encrypted storage
class LocationService {
  static const Uuid _uuid = Uuid();
  
  // Earth radius in meters for distance calculations
  static const double _earthRadiusMeters = 6371000;
  
  // Default geofence radius in meters
  static const double defaultGeofenceRadius = 500;
  
  // Threshold for considering a point "near" a route (in meters)
  static const double nearRouteThreshold = 200;

  /// Initialize the location service
  static Future<void> initialize() async {
    await SecureStorageService.initialize();
  }

  // ============================================================
  // ROUTE MANAGEMENT (Local Storage Only - Never Transmitted)
  // Requirements: 4.1, 7.3
  // ============================================================

  /// Store a route locally with encryption
  /// Requirements: 4.1, 7.3 - Route data stored locally only
  static Future<StoredRoute> storeRoute({
    required String name,
    required List<RoutePoint> points,
  }) async {
    final route = StoredRoute(
      id: _uuid.v4(),
      name: name,
      points: points,
      createdAt: DateTime.now(),
      lastUsed: DateTime.now(),
      usageCount: 1,
    );
    
    // Store encrypted route data
    await SecureStorageService.write(
      '${LocationStorageKeys.routesPrefix}${route.id}',
      jsonEncode(route.toJson()),
    );
    
    // Update route index
    await _addToRouteIndex(route.id);
    
    return route;
  }

  /// Get a stored route by ID
  static Future<StoredRoute?> getRoute(String routeId) async {
    final data = await SecureStorageService.read(
      '${LocationStorageKeys.routesPrefix}$routeId',
    );
    
    if (data == null) return null;
    
    return StoredRoute.fromJson(jsonDecode(data) as Map<String, dynamic>);
  }

  /// Get all stored routes
  static Future<List<StoredRoute>> getAllRoutes() async {
    final indexData = await SecureStorageService.read(LocationStorageKeys.routeIndex);
    if (indexData == null) return [];
    
    final routeIds = (jsonDecode(indexData) as List<dynamic>).cast<String>();
    final routes = <StoredRoute>[];
    
    for (final id in routeIds) {
      final route = await getRoute(id);
      if (route != null) {
        routes.add(route);
      }
    }
    
    return routes;
  }

  /// Update route usage (called when route is used)
  static Future<void> updateRouteUsage(String routeId) async {
    final route = await getRoute(routeId);
    if (route == null) return;
    
    final updatedRoute = route.copyWith(
      lastUsed: DateTime.now(),
      usageCount: route.usageCount + 1,
    );
    
    await SecureStorageService.write(
      '${LocationStorageKeys.routesPrefix}$routeId',
      jsonEncode(updatedRoute.toJson()),
    );
  }

  /// Delete a stored route
  static Future<void> deleteRoute(String routeId) async {
    await SecureStorageService.delete(
      '${LocationStorageKeys.routesPrefix}$routeId',
    );
    await _removeFromRouteIndex(routeId);
  }

  /// Delete all stored routes
  static Future<void> deleteAllRoutes() async {
    final routes = await getAllRoutes();
    for (final route in routes) {
      await SecureStorageService.delete(
        '${LocationStorageKeys.routesPrefix}${route.id}',
      );
    }
    await SecureStorageService.delete(LocationStorageKeys.routeIndex);
  }

  // ============================================================
  // GEOFENCE MANAGEMENT
  // Requirements: 4.3
  // ============================================================

  /// Create a geofence around a location
  /// Requirements: 4.3 - Create geofences around common locations
  static Future<Geofence> createGeofence({
    required String name,
    required GeoCoordinate center,
    double radiusMeters = defaultGeofenceRadius,
  }) async {
    final geofence = Geofence(
      id: _uuid.v4(),
      name: name,
      center: center,
      radiusMeters: radiusMeters,
      isActive: true,
    );
    
    await SecureStorageService.write(
      '${LocationStorageKeys.geofencesPrefix}${geofence.id}',
      jsonEncode(geofence.toJson()),
    );
    
    await _addToGeofenceIndex(geofence.id);
    
    return geofence;
  }

  /// Get a geofence by ID
  static Future<Geofence?> getGeofence(String geofenceId) async {
    final data = await SecureStorageService.read(
      '${LocationStorageKeys.geofencesPrefix}$geofenceId',
    );
    
    if (data == null) return null;
    
    return Geofence.fromJson(jsonDecode(data) as Map<String, dynamic>);
  }

  /// Get all geofences
  static Future<List<Geofence>> getAllGeofences() async {
    final indexData = await SecureStorageService.read(LocationStorageKeys.geofenceIndex);
    if (indexData == null) return [];
    
    final geofenceIds = (jsonDecode(indexData) as List<dynamic>).cast<String>();
    final geofences = <Geofence>[];
    
    for (final id in geofenceIds) {
      final geofence = await getGeofence(id);
      if (geofence != null) {
        geofences.add(geofence);
      }
    }
    
    return geofences;
  }

  /// Delete a geofence
  static Future<void> deleteGeofence(String geofenceId) async {
    await SecureStorageService.delete(
      '${LocationStorageKeys.geofencesPrefix}$geofenceId',
    );
    await _removeFromGeofenceIndex(geofenceId);
  }

  // ============================================================
  // CHECK REQUEST GENERATION (Privacy-Preserving)
  // Requirements: 4.2, 4.4
  // ============================================================

  /// Generate a location-aware check request
  /// Requirements: 4.2, 4.4 - Location context without revealing exact routes
  static Future<CheckRequest> generateCheckRequest({
    required String alertId,
    required String targetUserId,
    required GeoCoordinate currentLocation,
  }) async {
    // Get location context without revealing exact routes
    final context = await _generateLocationContext(currentLocation);
    
    // Check if near any known routes (local check only)
    final isNearRoute = await _isNearKnownRoute(currentLocation);
    
    return CheckRequest(
      id: _uuid.v4(),
      alertId: alertId,
      targetUserId: targetUserId,
      locationContext: context.description,
      createdAt: DateTime.now(),
      generalArea: context.generalArea,
      isNearKnownRoute: isNearRoute,
    );
  }

  /// Generate privacy-preserving location context
  /// Requirements: 4.4 - Include relevant location context without revealing exact routes
  static Future<LocationContext> _generateLocationContext(
    GeoCoordinate location,
  ) async {
    // Get nearby geofences for context
    final geofences = await getAllGeofences();
    String? nearbyLandmark;
    bool isNearCommonLocation = false;
    
    for (final geofence in geofences) {
      final distance = calculateDistance(location, geofence.center);
      if (distance <= geofence.radiusMeters) {
        nearbyLandmark = geofence.name;
        isNearCommonLocation = true;
        break;
      }
    }
    
    // Generate general area description (privacy-preserving)
    final generalArea = _getGeneralAreaDescription(location);
    
    // Build description without exact coordinates
    String description;
    if (nearbyLandmark != null) {
      description = 'Near $nearbyLandmark in $generalArea';
    } else {
      description = 'In $generalArea area';
    }
    
    return LocationContext(
      generalArea: generalArea,
      description: description,
      isNearCommonLocation: isNearCommonLocation,
      nearbyLandmark: nearbyLandmark,
    );
  }

  /// Check if a location is near any known routes (local check only)
  /// Requirements: 4.1 - Use locally stored route data without transmitting it
  static Future<bool> _isNearKnownRoute(GeoCoordinate location) async {
    final routes = await getAllRoutes();
    
    for (final route in routes) {
      for (final point in route.points) {
        final distance = calculateDistance(location, point.coordinate);
        if (distance <= nearRouteThreshold) {
          return true;
        }
      }
    }
    
    return false;
  }

  /// Get general area description (privacy-preserving)
  /// This provides context without revealing exact location
  static String _getGeneralAreaDescription(GeoCoordinate location) {
    // Round coordinates to reduce precision (privacy protection)
    // This gives approximately 1km precision
    final roundedLat = (location.latitude * 100).round() / 100;
    final roundedLng = (location.longitude * 100).round() / 100;
    
    // Generate a general area identifier
    // In production, this would use reverse geocoding with privacy settings
    return 'Area ${roundedLat.toStringAsFixed(2)}, ${roundedLng.toStringAsFixed(2)}';
  }

  // ============================================================
  // DISTANCE CALCULATIONS
  // ============================================================

  /// Calculate distance between two coordinates using Haversine formula
  static double calculateDistance(GeoCoordinate point1, GeoCoordinate point2) {
    final lat1Rad = _degreesToRadians(point1.latitude);
    final lat2Rad = _degreesToRadians(point2.latitude);
    final deltaLat = _degreesToRadians(point2.latitude - point1.latitude);
    final deltaLng = _degreesToRadians(point2.longitude - point1.longitude);
    
    final a = sin(deltaLat / 2) * sin(deltaLat / 2) +
        cos(lat1Rad) * cos(lat2Rad) * sin(deltaLng / 2) * sin(deltaLng / 2);
    final c = 2 * atan2(sqrt(a), sqrt(1 - a));
    
    return _earthRadiusMeters * c;
  }

  /// Check if a point is within a geofence
  static bool isWithinGeofence(GeoCoordinate point, Geofence geofence) {
    final distance = calculateDistance(point, geofence.center);
    return distance <= geofence.radiusMeters;
  }

  /// Find the nearest point on a route to a given location
  static RoutePoint? findNearestRoutePoint(
    GeoCoordinate location,
    StoredRoute route,
  ) {
    if (route.points.isEmpty) return null;
    
    RoutePoint? nearest;
    double minDistance = double.infinity;
    
    for (final point in route.points) {
      final distance = calculateDistance(location, point.coordinate);
      if (distance < minDistance) {
        minDistance = distance;
        nearest = point;
      }
    }
    
    return nearest;
  }

  // ============================================================
  // HELPER METHODS
  // ============================================================

  static double _degreesToRadians(double degrees) {
    return degrees * pi / 180;
  }

  static Future<void> _addToRouteIndex(String routeId) async {
    final indexData = await SecureStorageService.read(LocationStorageKeys.routeIndex);
    final routeIds = indexData != null
        ? (jsonDecode(indexData) as List<dynamic>).cast<String>()
        : <String>[];
    
    if (!routeIds.contains(routeId)) {
      routeIds.add(routeId);
      await SecureStorageService.write(
        LocationStorageKeys.routeIndex,
        jsonEncode(routeIds),
      );
    }
  }

  static Future<void> _removeFromRouteIndex(String routeId) async {
    final indexData = await SecureStorageService.read(LocationStorageKeys.routeIndex);
    if (indexData == null) return;
    
    final routeIds = (jsonDecode(indexData) as List<dynamic>).cast<String>();
    routeIds.remove(routeId);
    
    await SecureStorageService.write(
      LocationStorageKeys.routeIndex,
      jsonEncode(routeIds),
    );
  }

  static Future<void> _addToGeofenceIndex(String geofenceId) async {
    final indexData = await SecureStorageService.read(LocationStorageKeys.geofenceIndex);
    final geofenceIds = indexData != null
        ? (jsonDecode(indexData) as List<dynamic>).cast<String>()
        : <String>[];
    
    if (!geofenceIds.contains(geofenceId)) {
      geofenceIds.add(geofenceId);
      await SecureStorageService.write(
        LocationStorageKeys.geofenceIndex,
        jsonEncode(geofenceIds),
      );
    }
  }

  static Future<void> _removeFromGeofenceIndex(String geofenceId) async {
    final indexData = await SecureStorageService.read(LocationStorageKeys.geofenceIndex);
    if (indexData == null) return;
    
    final geofenceIds = (jsonDecode(indexData) as List<dynamic>).cast<String>();
    geofenceIds.remove(geofenceId);
    
    await SecureStorageService.write(
      LocationStorageKeys.geofenceIndex,
      jsonEncode(geofenceIds),
    );
  }

  // ============================================================
  // NETWORK TRANSMISSION PREVENTION
  // Requirements: 4.1, 4.5, 7.3
  // ============================================================

  /// Validate that route data is not being transmitted
  /// This is a safety check to ensure route data stays local
  static bool validateNoRouteDataInPayload(Map<String, dynamic> payload) {
    // Check for any route-related keys that shouldn't be transmitted
    final forbiddenKeys = [
      'route_points',
      'routePoints',
      'route_data',
      'routeData',
      'exact_coordinates',
      'exactCoordinates',
      'stored_routes',
      'storedRoutes',
    ];
    
    for (final key in forbiddenKeys) {
      if (payload.containsKey(key)) {
        return false;
      }
    }
    
    // Recursively check nested objects
    for (final value in payload.values) {
      if (value is Map<String, dynamic>) {
        if (!validateNoRouteDataInPayload(value)) {
          return false;
        }
      } else if (value is List) {
        for (final item in value) {
          if (item is Map<String, dynamic>) {
            if (!validateNoRouteDataInPayload(item)) {
              return false;
            }
          }
        }
      }
    }
    
    return true;
  }

  /// Create a safe payload for network transmission
  /// Strips any route data and ensures privacy
  static Map<String, dynamic> createSafeNetworkPayload({
    required String alertId,
    required LocationContext context,
    bool isNearKnownRoute = false,
  }) {
    // Only include privacy-safe information
    return {
      'alert_id': alertId,
      'general_area': context.generalArea,
      'description': context.description,
      'is_near_common_location': context.isNearCommonLocation,
      'nearby_landmark': context.nearbyLandmark,
      'is_near_known_route': isNearKnownRoute,
      // Explicitly NOT including:
      // - exact coordinates
      // - route points
      // - stored route data
    };
  }
}
