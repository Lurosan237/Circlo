import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:connectivity_plus/connectivity_plus.dart';

/// Error types for categorization
enum ErrorType {
  network,
  authentication,
  authorization,
  validation,
  server,
  timeout,
  offline,
  unknown,
}

/// Application error with user-friendly messaging
class AppError implements Exception {
  final String message;
  final String? code;
  final ErrorType type;
  final dynamic originalError;
  final StackTrace? stackTrace;
  final DateTime timestamp;
  final bool isRetryable;

  AppError({
    required this.message,
    this.code,
    required this.type,
    this.originalError,
    this.stackTrace,
    this.isRetryable = false,
  }) : timestamp = DateTime.now();

  /// Get user-friendly message based on error type
  String get userMessage {
    switch (type) {
      case ErrorType.network:
        return 'Unable to connect. Please check your internet connection.';
      case ErrorType.authentication:
        return 'Your session has expired. Please sign in again.';
      case ErrorType.authorization:
        return 'You don\'t have permission to perform this action.';
      case ErrorType.validation:
        return message;
      case ErrorType.server:
        return 'Something went wrong on our end. Please try again later.';
      case ErrorType.timeout:
        return 'The request took too long. Please try again.';
      case ErrorType.offline:
        return 'You\'re offline. Some features may be unavailable.';
      case ErrorType.unknown:
        return 'An unexpected error occurred. Please try again.';
    }
  }

  @override
  String toString() => 'AppError(type: $type, code: $code, message: $message)';
}

/// Error state for UI consumption
class ErrorState {
  final AppError? currentError;
  final List<AppError> errorHistory;
  final bool isOffline;

  const ErrorState({
    this.currentError,
    this.errorHistory = const [],
    this.isOffline = false,
  });

  ErrorState copyWith({
    AppError? currentError,
    List<AppError>? errorHistory,
    bool? isOffline,
    bool clearCurrentError = false,
  }) {
    return ErrorState(
      currentError: clearCurrentError ? null : (currentError ?? this.currentError),
      errorHistory: errorHistory ?? this.errorHistory,
      isOffline: isOffline ?? this.isOffline,
    );
  }
}


/// Error service notifier for global error handling
class ErrorServiceNotifier extends StateNotifier<ErrorState> {
  final Connectivity _connectivity;
  StreamSubscription<List<ConnectivityResult>>? _connectivitySubscription;
  
  /// Maximum errors to keep in history
  static const int _maxHistorySize = 50;

  ErrorServiceNotifier({Connectivity? connectivity})
      : _connectivity = connectivity ?? Connectivity(),
        super(const ErrorState()) {
    _initConnectivityListener();
  }

  void _initConnectivityListener() {
    _connectivitySubscription = _connectivity.onConnectivityChanged.listen(
      (results) {
        final isOffline = results.isEmpty || 
            results.every((r) => r == ConnectivityResult.none);
        if (state.isOffline != isOffline) {
          state = state.copyWith(isOffline: isOffline);
          if (isOffline) {
            _logError(AppError(
              message: 'Device went offline',
              type: ErrorType.offline,
              isRetryable: true,
            ));
          }
        }
      },
    );
  }

  /// Handle and categorize an error
  AppError handleError(dynamic error, [StackTrace? stackTrace]) {
    final appError = _categorizeError(error, stackTrace);
    _logError(appError);
    state = state.copyWith(
      currentError: appError,
      errorHistory: _addToHistory(appError),
    );
    return appError;
  }

  /// Categorize error into appropriate type
  AppError _categorizeError(dynamic error, StackTrace? stackTrace) {
    // Handle SocketException (network issues)
    if (error is SocketException) {
      return AppError(
        message: 'Network connection failed',
        code: 'NETWORK_ERROR',
        type: ErrorType.network,
        originalError: error,
        stackTrace: stackTrace,
        isRetryable: true,
      );
    }

    // Handle TimeoutException
    if (error is TimeoutException) {
      return AppError(
        message: 'Request timed out',
        code: 'TIMEOUT_ERROR',
        type: ErrorType.timeout,
        originalError: error,
        stackTrace: stackTrace,
        isRetryable: true,
      );
    }

    // Handle AppError (already categorized)
    if (error is AppError) {
      return error;
    }

    // Handle HTTP status code errors (from API responses)
    if (error is Map<String, dynamic>) {
      return _handleApiError(error, stackTrace);
    }

    // Default to unknown error
    return AppError(
      message: error?.toString() ?? 'Unknown error',
      code: 'UNKNOWN_ERROR',
      type: ErrorType.unknown,
      originalError: error,
      stackTrace: stackTrace,
    );
  }

  AppError _handleApiError(Map<String, dynamic> errorData, StackTrace? stackTrace) {
    final code = errorData['code'] as String? ?? 'UNKNOWN_ERROR';
    final message = errorData['message'] as String? ?? 'An error occurred';
    final statusCode = errorData['status_code'] as int?;

    ErrorType type;
    bool isRetryable = false;

    // Categorize by status code
    if (statusCode != null) {
      if (statusCode == 401) {
        type = ErrorType.authentication;
      } else if (statusCode == 403) {
        type = ErrorType.authorization;
      } else if (statusCode == 422 || statusCode == 400) {
        type = ErrorType.validation;
      } else if (statusCode >= 500) {
        type = ErrorType.server;
        isRetryable = true;
      } else {
        type = ErrorType.unknown;
      }
    } else {
      // Categorize by error code
      type = _getTypeFromCode(code);
      isRetryable = _isRetryableCode(code);
    }

    return AppError(
      message: message,
      code: code,
      type: type,
      originalError: errorData,
      stackTrace: stackTrace,
      isRetryable: isRetryable,
    );
  }

  ErrorType _getTypeFromCode(String code) {
    if (code.contains('AUTH') || code.contains('TOKEN')) {
      return ErrorType.authentication;
    }
    if (code.contains('PERMISSION') || code.contains('FORBIDDEN')) {
      return ErrorType.authorization;
    }
    if (code.contains('VALIDATION') || code.contains('INVALID')) {
      return ErrorType.validation;
    }
    if (code.contains('NETWORK') || code.contains('CONNECTION')) {
      return ErrorType.network;
    }
    if (code.contains('TIMEOUT')) {
      return ErrorType.timeout;
    }
    if (code.contains('SERVER') || code.contains('INTERNAL')) {
      return ErrorType.server;
    }
    return ErrorType.unknown;
  }

  bool _isRetryableCode(String code) {
    return code.contains('NETWORK') ||
        code.contains('TIMEOUT') ||
        code.contains('SERVER') ||
        code.contains('TEMPORARY');
  }

  List<AppError> _addToHistory(AppError error) {
    final history = [...state.errorHistory, error];
    if (history.length > _maxHistorySize) {
      return history.sublist(history.length - _maxHistorySize);
    }
    return history;
  }

  void _logError(AppError error) {
    // Log to console in debug mode
    if (kDebugMode) {
      debugPrint('=== ERROR LOG ===');
      debugPrint('Type: ${error.type}');
      debugPrint('Code: ${error.code}');
      debugPrint('Message: ${error.message}');
      debugPrint('Timestamp: ${error.timestamp}');
      if (error.stackTrace != null) {
        debugPrint('Stack trace: ${error.stackTrace}');
      }
      debugPrint('=================');
    }
    
    // In production, send to crash reporting service
    // Example: FirebaseCrashlytics.instance.recordError(error, error.stackTrace);
  }

  /// Clear current error
  void clearError() {
    state = state.copyWith(clearCurrentError: true);
  }

  /// Clear all error history
  void clearHistory() {
    state = state.copyWith(errorHistory: []);
  }

  /// Check current connectivity status
  Future<bool> checkConnectivity() async {
    final results = await _connectivity.checkConnectivity();
    final isOffline = results.isEmpty || 
        results.every((r) => r == ConnectivityResult.none);
    state = state.copyWith(isOffline: isOffline);
    return !isOffline;
  }

  @override
  void dispose() {
    _connectivitySubscription?.cancel();
    super.dispose();
  }
}


/// Retry configuration for failed operations
class RetryConfig {
  final int maxAttempts;
  final Duration initialDelay;
  final double backoffMultiplier;
  final Duration maxDelay;

  const RetryConfig({
    this.maxAttempts = 3,
    this.initialDelay = const Duration(seconds: 1),
    this.backoffMultiplier = 2.0,
    this.maxDelay = const Duration(seconds: 30),
  });

  Duration getDelayForAttempt(int attempt) {
    final delay = initialDelay * (backoffMultiplier * attempt);
    return delay > maxDelay ? maxDelay : delay;
  }
}

/// Retry helper for operations with exponential backoff
class RetryHelper {
  final ErrorServiceNotifier errorService;
  final RetryConfig config;

  RetryHelper({
    required this.errorService,
    this.config = const RetryConfig(),
  });

  /// Execute operation with retry logic
  Future<T> execute<T>(
    Future<T> Function() operation, {
    bool Function(dynamic error)? shouldRetry,
    void Function(int attempt, Duration delay)? onRetry,
  }) async {
    int attempt = 0;
    
    while (true) {
      try {
        attempt++;
        return await operation();
      } catch (error, stackTrace) {
        final appError = errorService.handleError(error, stackTrace);
        
        // Check if we should retry
        final canRetry = appError.isRetryable &&
            attempt < config.maxAttempts &&
            (shouldRetry?.call(error) ?? true);

        if (!canRetry) {
          throw appError;
        }

        // Wait before retrying with exponential backoff
        final delay = config.getDelayForAttempt(attempt);
        onRetry?.call(attempt, delay);
        
        // Check connectivity before retrying network errors
        if (appError.type == ErrorType.network || 
            appError.type == ErrorType.offline) {
          final isOnline = await errorService.checkConnectivity();
          if (!isOnline) {
            throw appError;
          }
        }

        await Future.delayed(delay);
      }
    }
  }
}

/// Pending operation for offline queue
class PendingOperation {
  final String id;
  final String type;
  final Map<String, dynamic> data;
  final DateTime createdAt;
  int retryCount;

  PendingOperation({
    required this.id,
    required this.type,
    required this.data,
    DateTime? createdAt,
    this.retryCount = 0,
  }) : createdAt = createdAt ?? DateTime.now();

  Map<String, dynamic> toJson() => {
    'id': id,
    'type': type,
    'data': data,
    'createdAt': createdAt.toIso8601String(),
    'retryCount': retryCount,
  };

  factory PendingOperation.fromJson(Map<String, dynamic> json) => PendingOperation(
    id: json['id'] as String,
    type: json['type'] as String,
    data: json['data'] as Map<String, dynamic>,
    createdAt: DateTime.parse(json['createdAt'] as String),
    retryCount: json['retryCount'] as int? ?? 0,
  );
}

/// Offline queue for storing failed operations
class OfflineQueue {
  final List<PendingOperation> _queue = [];
  final int maxQueueSize;
  final int maxRetries;

  OfflineQueue({
    this.maxQueueSize = 100,
    this.maxRetries = 5,
  });

  List<PendingOperation> get pending => List.unmodifiable(_queue);
  int get length => _queue.length;
  bool get isEmpty => _queue.isEmpty;
  bool get isNotEmpty => _queue.isNotEmpty;

  /// Add operation to queue
  void enqueue(PendingOperation operation) {
    if (_queue.length >= maxQueueSize) {
      // Remove oldest operation
      _queue.removeAt(0);
    }
    _queue.add(operation);
  }

  /// Remove operation from queue
  void dequeue(String operationId) {
    _queue.removeWhere((op) => op.id == operationId);
  }

  /// Get next operation to process
  PendingOperation? peek() {
    if (_queue.isEmpty) return null;
    return _queue.first;
  }

  /// Increment retry count and check if should remove
  bool incrementRetry(String operationId) {
    final index = _queue.indexWhere((op) => op.id == operationId);
    if (index == -1) return false;
    
    _queue[index].retryCount++;
    if (_queue[index].retryCount >= maxRetries) {
      _queue.removeAt(index);
      return false; // Operation removed due to max retries
    }
    return true; // Operation still in queue
  }

  /// Clear all pending operations
  void clear() {
    _queue.clear();
  }
}

// Riverpod providers
final errorServiceProvider = StateNotifierProvider<ErrorServiceNotifier, ErrorState>(
  (ref) => ErrorServiceNotifier(),
);

final currentErrorProvider = Provider<AppError?>((ref) {
  return ref.watch(errorServiceProvider).currentError;
});

final isOfflineProvider = Provider<bool>((ref) {
  return ref.watch(errorServiceProvider).isOffline;
});

final retryHelperProvider = Provider<RetryHelper>((ref) {
  return RetryHelper(
    errorService: ref.read(errorServiceProvider.notifier),
  );
});

final offlineQueueProvider = Provider<OfflineQueue>((ref) {
  return OfflineQueue();
});
