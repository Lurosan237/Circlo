/// Location feature module
/// 
/// Requirements:
/// - 4.1: Use locally stored route data without transmitting it
/// - 4.2: Send targeted check requests when near known routes
/// - 4.3: Create geofences around common locations
/// - 4.4: Include relevant location context without revealing exact routes
/// - 4.5: Never store or transmit persistent location data
/// - 7.3: Store route data only locally using Hive encrypted storage

export 'data/location_repository.dart';
