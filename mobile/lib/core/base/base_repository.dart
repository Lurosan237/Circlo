import '../services/api_service.dart';

/// Base repository class providing common patterns for data access
abstract class BaseRepository {
  final ApiService apiService;

  BaseRepository({required this.apiService});
}

/// Result wrapper for repository operations
class Result<T> {
  final T? data;
  final String? error;
  final String? errorCode;
  final bool isSuccess;

  Result._({
    this.data,
    this.error,
    this.errorCode,
    required this.isSuccess,
  });

  factory Result.success(T data) => Result._(
    data: data,
    isSuccess: true,
  );

  factory Result.failure(String error, {String? code}) => Result._(
    error: error,
    errorCode: code,
    isSuccess: false,
  );

  /// Map the result to a different type
  Result<R> map<R>(R Function(T) mapper) {
    if (isSuccess && data != null) {
      return Result.success(mapper(data as T));
    }
    return Result.failure(error ?? 'Unknown error', code: errorCode);
  }

  /// Execute a function if successful
  void onSuccess(void Function(T) action) {
    if (isSuccess && data != null) {
      action(data as T);
    }
  }

  /// Execute a function if failed
  void onFailure(void Function(String, String?) action) {
    if (!isSuccess) {
      action(error ?? 'Unknown error', errorCode);
    }
  }
}
