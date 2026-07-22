import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/models/user.dart';
import '../../../../core/services/api_service.dart';
import '../../data/auth_repository.dart';

/// Authentication state
class AuthState {
  final bool isLoading;
  final bool isAuthenticated;
  final User? user;
  final String? error;
  final String? errorCode;

  const AuthState({
    this.isLoading = false,
    this.isAuthenticated = false,
    this.user,
    this.error,
    this.errorCode,
  });

  AuthState copyWith({
    bool? isLoading,
    bool? isAuthenticated,
    User? user,
    String? error,
    String? errorCode,
    bool clearUser = false,
    bool clearError = false,
  }) {
    return AuthState(
      isLoading: isLoading ?? this.isLoading,
      isAuthenticated: isAuthenticated ?? this.isAuthenticated,
      user: clearUser ? null : (user ?? this.user),
      error: clearError ? null : (error ?? this.error),
      errorCode: clearError ? null : (errorCode ?? this.errorCode),
    );
  }
}

/// API Service provider
final apiServiceProvider = Provider<ApiService>((ref) {
  // TODO: Configure with actual base URL from environment
  return ApiService(baseUrl: 'http://localhost:8000/api/v1');
});

/// Auth Repository provider
final authRepositoryProvider = Provider<AuthRepository>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  return AuthRepository(apiService: apiService);
});

/// Auth Controller provider using Riverpod
/// Requirements: 9.2 - Riverpod for state management
final authControllerProvider =
    StateNotifierProvider<AuthController, AuthState>((ref) {
  final repository = ref.watch(authRepositoryProvider);
  return AuthController(repository);
});

/// Authentication controller managing auth state
/// Requirements: 9.2 - Riverpod for state management
class AuthController extends StateNotifier<AuthState> {
  final AuthRepository _repository;
  Timer? _tokenRefreshTimer;

  AuthController(this._repository) : super(const AuthState()) {
    // Check initial authentication status
    _checkAuthStatus();
  }

  /// Check if user is already authenticated
  Future<void> _checkAuthStatus() async {
    state = state.copyWith(isLoading: true, clearError: true);
    
    try {
      final isAuthenticated = await _repository.isAuthenticated();
      
      if (isAuthenticated) {
        // Try to get current user
        final result = await _repository.getCurrentUser();
        
        if (result.isSuccess && result.data != null) {
          state = state.copyWith(
            isLoading: false,
            isAuthenticated: true,
            user: result.data,
          );
          _startTokenRefreshTimer();
          return;
        }
      }
      
      state = state.copyWith(
        isLoading: false,
        isAuthenticated: false,
        clearUser: true,
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        isAuthenticated: false,
        clearUser: true,
      );
    }
  }

  /// Register a new user
  /// Requirements: 1.1 - Phone number hashing before transmission
  Future<bool> register({
    required String phoneNumber,
    required String name,
    required String password,
  }) async {
    state = state.copyWith(isLoading: true, clearError: true);

    final result = await _repository.register(
      phoneNumber: phoneNumber,
      name: name,
      password: password,
    );

    if (result.isSuccess) {
      // Get user info after registration
      final userResult = await _repository.getCurrentUser();
      
      state = state.copyWith(
        isLoading: false,
        isAuthenticated: true,
        user: userResult.data,
      );
      
      _startTokenRefreshTimer();
      return true;
    }

    state = state.copyWith(
      isLoading: false,
      error: result.error,
      errorCode: result.errorCode,
    );
    return false;
  }

  /// Login with phone number and password
  /// Requirements: 1.1 - Phone number hashing before transmission
  /// Requirements: 1.2 - JWT token with 24-hour expiry
  Future<bool> login({
    required String phoneNumber,
    required String password,
  }) async {
    state = state.copyWith(isLoading: true, clearError: true);

    final result = await _repository.login(
      phoneNumber: phoneNumber,
      password: password,
    );

    if (result.isSuccess) {
      // Get user info after login
      final userResult = await _repository.getCurrentUser();
      
      state = state.copyWith(
        isLoading: false,
        isAuthenticated: true,
        user: userResult.data,
      );
      
      _startTokenRefreshTimer();
      return true;
    }

    state = state.copyWith(
      isLoading: false,
      error: result.error,
      errorCode: result.errorCode,
    );
    return false;
  }

  /// Logout user
  Future<void> logout() async {
    state = state.copyWith(isLoading: true, clearError: true);
    
    _stopTokenRefreshTimer();
    
    await _repository.logout();

    state = const AuthState(
      isLoading: false,
      isAuthenticated: false,
    );
  }

  /// Refresh authentication token
  /// Requirements: 1.2 - JWT token with 24-hour expiry
  Future<bool> refreshToken() async {
    final result = await _repository.refreshToken();

    if (result.isSuccess) {
      return true;
    }

    // If refresh fails, logout user
    await logout();
    return false;
  }

  /// Start automatic token refresh timer
  /// Refreshes token 1 hour before expiry (23 hours after login)
  void _startTokenRefreshTimer() {
    _stopTokenRefreshTimer();
    
    // Refresh token 1 hour before expiry (23 hours = 82800 seconds)
    const refreshInterval = Duration(hours: 23);
    
    _tokenRefreshTimer = Timer.periodic(refreshInterval, (_) async {
      await refreshToken();
    });
  }

  /// Stop token refresh timer
  void _stopTokenRefreshTimer() {
    _tokenRefreshTimer?.cancel();
    _tokenRefreshTimer = null;
  }

  /// Clear any error state
  void clearError() {
    state = state.copyWith(clearError: true);
  }

  @override
  void dispose() {
    _stopTokenRefreshTimer();
    super.dispose();
  }
}
