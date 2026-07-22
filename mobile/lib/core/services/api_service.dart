import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'error_service.dart';

/// API response wrapper for consistent response handling
class ApiResponse<T> {
  final bool success;
  final String? message;
  final String? code;
  final T? data;

  ApiResponse({
    required this.success,
    this.message,
    this.code,
    this.data,
  });

  factory ApiResponse.fromJson(
    Map<String, dynamic> json,
    T Function(dynamic)? fromJsonT,
  ) {
    return ApiResponse(
      success: json['success'] as bool,
      message: json['message'] as String?,
      code: json['code'] as String?,
      data: json['data'] != null && fromJsonT != null
          ? fromJsonT(json['data'])
          : json['data'] as T?,
    );
  }

  /// Convert to AppError if not successful
  AppError? toAppError() {
    if (success) return null;
    return AppError(
      message: message ?? 'An error occurred',
      code: code,
      type: _getErrorType(),
      isRetryable: _isRetryable(),
    );
  }

  ErrorType _getErrorType() {
    if (code == null) return ErrorType.unknown;
    if (code!.contains('AUTH') || code!.contains('TOKEN')) {
      return ErrorType.authentication;
    }
    if (code!.contains('PERMISSION') || code!.contains('FORBIDDEN')) {
      return ErrorType.authorization;
    }
    if (code!.contains('VALIDATION') || code!.contains('INVALID')) {
      return ErrorType.validation;
    }
    if (code!.contains('NETWORK')) {
      return ErrorType.network;
    }
    if (code!.contains('SERVER')) {
      return ErrorType.server;
    }
    return ErrorType.unknown;
  }

  bool _isRetryable() {
    if (code == null) return false;
    return code!.contains('NETWORK') ||
        code!.contains('TIMEOUT') ||
        code!.contains('SERVER');
  }
}

/// Centralized API service with JWT token management
class ApiService {
  static const String _tokenKey = 'auth_token';
  static const String _refreshTokenKey = 'refresh_token';
  static const FlutterSecureStorage _secureStorage = FlutterSecureStorage();
  
  late final Dio _dio;
  final String baseUrl;

  ApiService({required this.baseUrl}) {
    _dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 30),
      receiveTimeout: const Duration(seconds: 30),
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    ));

    _setupInterceptors();
  }

  void _setupInterceptors() {
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        // Add auth token to requests
        final token = await _secureStorage.read(key: _tokenKey);
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
      onError: (error, handler) async {
        // Handle 401 errors with token refresh
        if (error.response?.statusCode == 401) {
          final refreshed = await _refreshToken();
          if (refreshed) {
            // Retry the request
            final retryResponse = await _retry(error.requestOptions);
            handler.resolve(retryResponse);
            return;
          }
        }
        handler.next(error);
      },
    ));
  }

  Future<bool> _refreshToken() async {
    try {
      final refreshToken = await _secureStorage.read(key: _refreshTokenKey);
      if (refreshToken == null) return false;

      final response = await _dio.post(
        '/auth/refresh',
        data: {'refresh_token': refreshToken},
      );

      if (response.statusCode == 200 && response.data['success'] == true) {
        await _secureStorage.write(
          key: _tokenKey,
          value: response.data['data']['access_token'],
        );
        return true;
      }
      return false;
    } catch (e) {
      return false;
    }
  }

  Future<Response> _retry(RequestOptions requestOptions) async {
    final token = await _secureStorage.read(key: _tokenKey);
    final options = Options(
      method: requestOptions.method,
      headers: {
        ...requestOptions.headers,
        'Authorization': 'Bearer $token',
      },
    );

    return _dio.request(
      requestOptions.path,
      data: requestOptions.data,
      queryParameters: requestOptions.queryParameters,
      options: options,
    );
  }

  /// Store authentication tokens
  Future<void> setTokens({
    required String accessToken,
    String? refreshToken,
  }) async {
    await _secureStorage.write(key: _tokenKey, value: accessToken);
    if (refreshToken != null) {
      await _secureStorage.write(key: _refreshTokenKey, value: refreshToken);
    }
  }

  /// Clear authentication tokens
  Future<void> clearTokens() async {
    await _secureStorage.delete(key: _tokenKey);
    await _secureStorage.delete(key: _refreshTokenKey);
  }

  /// Check if user is authenticated
  Future<bool> isAuthenticated() async {
    final token = await _secureStorage.read(key: _tokenKey);
    return token != null;
  }

  /// GET request
  Future<ApiResponse<T>> get<T>(
    String path, {
    Map<String, dynamic>? queryParameters,
    T Function(dynamic)? fromJsonT,
  }) async {
    try {
      final response = await _dio.get(path, queryParameters: queryParameters);
      return ApiResponse.fromJson(response.data, fromJsonT);
    } on DioException catch (e) {
      return _handleError(e);
    }
  }

  /// POST request
  Future<ApiResponse<T>> post<T>(
    String path, {
    dynamic data,
    T Function(dynamic)? fromJsonT,
  }) async {
    try {
      final response = await _dio.post(path, data: data);
      return ApiResponse.fromJson(response.data, fromJsonT);
    } on DioException catch (e) {
      return _handleError(e);
    }
  }

  /// PUT request
  Future<ApiResponse<T>> put<T>(
    String path, {
    dynamic data,
    T Function(dynamic)? fromJsonT,
  }) async {
    try {
      final response = await _dio.put(path, data: data);
      return ApiResponse.fromJson(response.data, fromJsonT);
    } on DioException catch (e) {
      return _handleError(e);
    }
  }

  /// DELETE request
  Future<ApiResponse<T>> delete<T>(
    String path, {
    T Function(dynamic)? fromJsonT,
  }) async {
    try {
      final response = await _dio.delete(path);
      return ApiResponse.fromJson(response.data, fromJsonT);
    } on DioException catch (e) {
      return _handleError(e);
    }
  }

  ApiResponse<T> _handleError<T>(DioException e) {
    final responseData = e.response?.data;
    final statusCode = e.response?.statusCode;
    
    String message;
    String code;
    
    if (responseData is Map<String, dynamic>) {
      message = responseData['message'] ?? _getDefaultMessage(e.type);
      code = responseData['code'] ?? _getDefaultCode(e.type, statusCode);
    } else {
      message = _getDefaultMessage(e.type);
      code = _getDefaultCode(e.type, statusCode);
    }

    return ApiResponse(
      success: false,
      message: message,
      code: code,
    );
  }

  String _getDefaultMessage(DioExceptionType type) {
    switch (type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return 'Request timed out. Please try again.';
      case DioExceptionType.connectionError:
        return 'Unable to connect. Please check your internet connection.';
      case DioExceptionType.badResponse:
        return 'Server returned an error. Please try again.';
      case DioExceptionType.cancel:
        return 'Request was cancelled.';
      default:
        return 'An unexpected error occurred.';
    }
  }

  String _getDefaultCode(DioExceptionType type, int? statusCode) {
    if (statusCode != null) {
      if (statusCode == 401) return 'AUTH_ERROR';
      if (statusCode == 403) return 'FORBIDDEN_ERROR';
      if (statusCode == 404) return 'NOT_FOUND_ERROR';
      if (statusCode == 422) return 'VALIDATION_ERROR';
      if (statusCode >= 500) return 'SERVER_ERROR';
    }
    
    switch (type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return 'TIMEOUT_ERROR';
      case DioExceptionType.connectionError:
        return 'NETWORK_ERROR';
      default:
        return 'UNKNOWN_ERROR';
    }
  }
}
