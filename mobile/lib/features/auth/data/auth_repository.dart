import '../../../core/base/base_repository.dart';
import '../../../core/services/api_service.dart';
import '../../../core/services/security_service.dart';
import '../../../core/models/user.dart';

/// Authentication result containing token and user data
class AuthenticationResult {
  final String accessToken;
  final String tokenType;
  final int expiresIn;
  final User? user;

  AuthenticationResult({
    required this.accessToken,
    required this.tokenType,
    required this.expiresIn,
    this.user,
  });

  factory AuthenticationResult.fromJson(Map<String, dynamic> json) {
    return AuthenticationResult(
      accessToken: json['access_token'] as String,
      tokenType: json['token_type'] as String? ?? 'bearer',
      expiresIn: json['expires_in'] as int? ?? 86400,
    );
  }
}

/// Repository for authentication operations
/// Implements secure phone hashing before transmission
/// Requirements: 1.1 - Phone number hashing before transmission
class AuthRepository extends BaseRepository {
  AuthRepository({required super.apiService});

  /// Register a new user
  /// Phone number is hashed locally using SHA-256 before transmission
  /// Requirements: 1.1 - Phone number hashing before transmission
  Future<Result<AuthenticationResult>> register({
    required String phoneNumber,
    required String name,
    required String password,
  }) async {
    // Hash phone number locally before transmission
    final phoneHash = SecurityService.hashPhoneNumber(phoneNumber);
    
    // Encrypt name for privacy
    final nameEncrypted = SecurityService.encryptData(name);
    
    final response = await apiService.post<Map<String, dynamic>>(
      '/auth/register',
      data: {
        'phone_hash': phoneHash,
        'name_encrypted': nameEncrypted.ciphertext,
        'password': password,
      },
    );

    if (response.success && response.data != null) {
      final result = AuthenticationResult.fromJson(response.data!);
      
      // Store tokens securely
      await apiService.setTokens(accessToken: result.accessToken);
      
      return Result.success(result);
    }

    return Result.failure(
      response.message ?? 'Registration failed',
      code: response.code,
    );
  }

  /// Login with phone number and password
  /// Phone number is hashed locally using SHA-256 before transmission
  /// Requirements: 1.1 - Phone number hashing before transmission
  /// Requirements: 1.2 - JWT token with 24-hour expiry
  Future<Result<AuthenticationResult>> login({
    required String phoneNumber,
    required String password,
  }) async {
    // Hash phone number locally before transmission
    final phoneHash = SecurityService.hashPhoneNumber(phoneNumber);
    
    final response = await apiService.post<Map<String, dynamic>>(
      '/auth/login',
      data: {
        'phone_hash': phoneHash,
        'password': password,
      },
    );

    if (response.success && response.data != null) {
      final result = AuthenticationResult.fromJson(response.data!);
      
      // Store tokens securely
      await apiService.setTokens(accessToken: result.accessToken);
      
      return Result.success(result);
    }

    return Result.failure(
      response.message ?? 'Login failed',
      code: response.code,
    );
  }

  /// Logout user and clear tokens
  Future<Result<void>> logout() async {
    final response = await apiService.post<void>('/auth/logout');
    
    // Clear tokens regardless of response
    await apiService.clearTokens();
    await SecurityService.clearKeys();
    
    if (response.success) {
      return Result.success(null);
    }

    // Still return success since tokens are cleared
    return Result.success(null);
  }

  /// Refresh authentication token
  /// Requirements: 1.2 - JWT token with 24-hour expiry
  Future<Result<AuthenticationResult>> refreshToken() async {
    final response = await apiService.post<Map<String, dynamic>>(
      '/auth/refresh',
    );

    if (response.success && response.data != null) {
      final result = AuthenticationResult.fromJson(response.data!);
      
      // Store new token
      await apiService.setTokens(accessToken: result.accessToken);
      
      return Result.success(result);
    }

    return Result.failure(
      response.message ?? 'Token refresh failed',
      code: response.code,
    );
  }

  /// Get current user information
  Future<Result<User>> getCurrentUser() async {
    final response = await apiService.get<Map<String, dynamic>>(
      '/auth/me',
    );

    if (response.success && response.data != null) {
      final userData = response.data!;
      final user = User(
        id: userData['id'] as String,
        phoneHash: userData['phone_hash'] as String,
        nameEncrypted: userData['name_encrypted'] as String,
        createdAt: DateTime.parse(userData['created_at'] as String),
        lastActive: DateTime.parse(userData['last_active'] as String),
      );
      
      return Result.success(user);
    }

    return Result.failure(
      response.message ?? 'Failed to get user',
      code: response.code,
    );
  }

  /// Check if user is authenticated
  Future<bool> isAuthenticated() async {
    return await apiService.isAuthenticated();
  }
}
