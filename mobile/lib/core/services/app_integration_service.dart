import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'api_service.dart';
import 'realtime_service.dart';
import 'security_service.dart';
import 'secure_storage_service.dart';
import 'location_service.dart';
import 'error_service.dart';
import '../../features/auth/data/auth_repository.dart';
import '../../features/circles/data/circle_repository.dart';
import '../../features/alerts/data/alert_repository.dart';
import '../../features/realtime/data/message_repository.dart';
import '../../features/location/data/location_repository.dart';

/// Configuration for the app integration
class AppConfig {
  final String apiBaseUrl;
  final String realtimeServerUrl;
  final bool enableDebugLogging;

  const AppConfig({
    required this.apiBaseUrl,
    required this.realtimeServerUrl,
    this.enableDebugLogging = false,
  });

  /// Default development configuration
  factory AppConfig.development() => const AppConfig(
    apiBaseUrl: 'http://localhost:8000/api/v1',
    realtimeServerUrl: 'http://localhost:8000',
    enableDebugLogging: true,
  );

  /// Production configuration
  factory AppConfig.production() => const AppConfig(
    apiBaseUrl: 'https://api.circlo.app/api/v1',
    realtimeServerUrl: 'https://api.circlo.app',
    enableDebugLogging: false,
  );
}

/// App configuration provider
final appConfigProvider = Provider<AppConfig>((ref) {
  // Default to development config, can be overridden
  return AppConfig.development();
});

/// API service provider
final apiServiceProvider = Provider<ApiService>((ref) {
  final config = ref.watch(appConfigProvider);
  return ApiService(baseUrl: config.apiBaseUrl);
});

/// Realtime service provider
final realtimeServiceProvider = Provider<RealtimeService>((ref) {
  final config = ref.watch(appConfigProvider);
  return RealtimeService(serverUrl: config.realtimeServerUrl);
});

/// Auth repository provider
final authRepositoryProvider = Provider<AuthRepository>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  return AuthRepository(apiService: apiService);
});

/// Circle repository provider
final circleRepositoryProvider = Provider<CircleRepository>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  return CircleRepository(apiService: apiService);
});

/// Alert repository provider
final alertRepositoryProvider = Provider<AlertRepository>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  return AlertRepository(apiService: apiService);
});

/// Message repository provider
final messageRepositoryProvider = Provider<MessageRepository>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  final realtimeService = ref.watch(realtimeServiceProvider);
  return MessageRepository(
    apiService: apiService,
    realtimeService: realtimeService,
  );
});

/// Location repository provider
final locationRepositoryProvider = Provider<LocationRepository>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  return LocationRepository(apiService: apiService);
});

/// App initialization state
enum AppInitState {
  uninitialized,
  initializing,
  initialized,
  error,
}

/// App integration state
class AppIntegrationState {
  final AppInitState initState;
  final bool isAuthenticated;
  final bool isRealtimeConnected;
  final String? error;

  const AppIntegrationState({
    this.initState = AppInitState.uninitialized,
    this.isAuthenticated = false,
    this.isRealtimeConnected = false,
    this.error,
  });

  AppIntegrationState copyWith({
    AppInitState? initState,
    bool? isAuthenticated,
    bool? isRealtimeConnected,
    String? error,
  }) {
    return AppIntegrationState(
      initState: initState ?? this.initState,
      isAuthenticated: isAuthenticated ?? this.isAuthenticated,
      isRealtimeConnected: isRealtimeConnected ?? this.isRealtimeConnected,
      error: error,
    );
  }
}

/// App integration service that wires all components together
/// Requirements: All requirements - Comprehensive integration between all modules
class AppIntegrationService extends StateNotifier<AppIntegrationState> {
  final ApiService _apiService;
  final RealtimeService _realtimeService;
  final AuthRepository _authRepository;
  
  StreamSubscription<ConnectionState>? _connectionSubscription;
  StreamSubscription<AlertUpdate>? _alertUpdateSubscription;

  AppIntegrationService({
    required ApiService apiService,
    required RealtimeService realtimeService,
    required AuthRepository authRepository,
  })  : _apiService = apiService,
        _realtimeService = realtimeService,
        _authRepository = authRepository,
        super(const AppIntegrationState());

  /// Initialize all app services
  Future<void> initialize() async {
    state = state.copyWith(initState: AppInitState.initializing);

    try {
      // Initialize security service
      await SecurityService.initialize();

      // Initialize secure storage
      await SecureStorageService.initialize();

      // Initialize location service
      await LocationService.initialize();

      // Check authentication status
      final isAuthenticated = await _authRepository.isAuthenticated();

      // If authenticated, connect to realtime service
      if (isAuthenticated) {
        await _connectRealtime();
      }

      state = state.copyWith(
        initState: AppInitState.initialized,
        isAuthenticated: isAuthenticated,
      );
    } catch (e) {
      state = state.copyWith(
        initState: AppInitState.error,
        error: e.toString(),
      );
    }
  }

  /// Connect to realtime service
  Future<void> _connectRealtime() async {
    final connected = await _realtimeService.connect();
    
    if (connected) {
      // Listen to connection state changes
      _connectionSubscription = _realtimeService.connectionState.listen((connectionState) {
        state = state.copyWith(
          isRealtimeConnected: connectionState == ConnectionState.connected,
        );
      });

      // Listen to alert updates for global handling
      _alertUpdateSubscription = _realtimeService.alertUpdates.listen(_handleAlertUpdate);
    }

    state = state.copyWith(isRealtimeConnected: connected);
  }

  /// Handle global alert updates
  void _handleAlertUpdate(AlertUpdate update) {
    // This can be used for global alert handling like showing notifications
    // The specific alert pages will also receive these updates through their own subscriptions
  }

  /// Handle user login
  Future<void> onUserLogin() async {
    state = state.copyWith(isAuthenticated: true);
    await _connectRealtime();
  }

  /// Handle user logout
  Future<void> onUserLogout() async {
    // Disconnect realtime
    _realtimeService.disconnect();
    
    // Clear tokens
    await _apiService.clearTokens();
    
    // Clear security keys
    await SecurityService.clearKeys();

    state = state.copyWith(
      isAuthenticated: false,
      isRealtimeConnected: false,
    );
  }

  /// Join an alert channel for real-time updates
  Future<void> joinAlertChannel(String alertId) async {
    if (!state.isRealtimeConnected) {
      await _connectRealtime();
    }
    await _realtimeService.joinAlert(alertId);
  }

  /// Leave an alert channel
  void leaveAlertChannel(String alertId) {
    _realtimeService.leaveAlert(alertId);
  }

  @override
  void dispose() {
    _connectionSubscription?.cancel();
    _alertUpdateSubscription?.cancel();
    _realtimeService.dispose();
    super.dispose();
  }
}

/// App integration service provider
final appIntegrationServiceProvider =
    StateNotifierProvider<AppIntegrationService, AppIntegrationState>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  final realtimeService = ref.watch(realtimeServiceProvider);
  final authRepository = ref.watch(authRepositoryProvider);

  return AppIntegrationService(
    apiService: apiService,
    realtimeService: realtimeService,
    authRepository: authRepository,
  );
});
