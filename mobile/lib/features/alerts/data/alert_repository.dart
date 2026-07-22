import '../../../core/base/base_repository.dart';
import '../../../core/services/api_service.dart';
import '../../../core/models/alert.dart';

/// Escalation info model
class EscalationInfo {
  final int currentLevel;
  final int nextLevel;
  final DateTime escalatedAt;
  final String targetCircle;

  EscalationInfo({
    required this.currentLevel,
    required this.nextLevel,
    required this.escalatedAt,
    required this.targetCircle,
  });

  factory EscalationInfo.fromJson(Map<String, dynamic> json) {
    return EscalationInfo(
      currentLevel: json['current_level'] as int,
      nextLevel: json['next_level'] as int,
      escalatedAt: DateTime.parse(json['escalated_at'] as String),
      targetCircle: json['target_circle'] as String,
    );
  }
}

/// Alert with verifications model
class AlertWithVerifications {
  final Alert alert;
  final List<AlertVerification> verifications;

  AlertWithVerifications({
    required this.alert,
    required this.verifications,
  });

  factory AlertWithVerifications.fromJson(Map<String, dynamic> json) {
    final verificationsList = (json['verifications'] as List<dynamic>?)
            ?.map((v) => AlertVerification.fromJson(v as Map<String, dynamic>))
            .toList() ??
        [];

    return AlertWithVerifications(
      alert: Alert(
        id: json['id'] as String,
        userId: json['user_id'] as String,
        type: AlertType.values.firstWhere(
          (e) => e.name == json['type'],
          orElse: () => AlertType.missing,
        ),
        status: AlertStatus.values.firstWhere(
          (e) => e.name == json['status'],
          orElse: () => AlertStatus.pending,
        ),
        verificationCount: json['verification_count'] as int,
        requiredVerifications: json['required_verifications'] as int,
        escalationLevel: json['escalation_level'] as int,
        createdAt: DateTime.parse(json['created_at'] as String),
        escalatedAt: json['escalated_at'] != null
            ? DateTime.parse(json['escalated_at'] as String)
            : null,
        resolvedAt: json['resolved_at'] != null
            ? DateTime.parse(json['resolved_at'] as String)
            : null,
      ),
      verifications: verificationsList,
    );
  }
}

/// Repository for alert management operations
/// Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
class AlertRepository extends BaseRepository {
  AlertRepository({required super.apiService});

  /// Create a new alert requiring multi-person verification
  /// Requirements: 3.1 - Multi-person verification requirement
  Future<Result<AlertWithVerifications>> createAlert({
    required AlertType type,
  }) async {
    final response = await apiService.post<Map<String, dynamic>>(
      '/alerts',
      data: {'type': type.name},
    );

    if (response.success && response.data != null) {
      final alertData = response.data!['data'] as Map<String, dynamic>?;
      if (alertData != null) {
        return Result.success(AlertWithVerifications.fromJson(alertData));
      }
    }

    return Result.failure(
      response.message ?? 'Failed to create alert',
      code: response.code,
    );
  }

  /// Get all alerts for the current user
  Future<Result<List<AlertWithVerifications>>> getMyAlerts({
    bool includeResolved = false,
  }) async {
    final response = await apiService.get<Map<String, dynamic>>(
      '/alerts',
      queryParameters: {'include_resolved': includeResolved.toString()},
    );

    if (response.success && response.data != null) {
      final dataList = response.data!['data'] as List<dynamic>?;
      if (dataList != null) {
        final alerts = dataList
            .map((json) =>
                AlertWithVerifications.fromJson(json as Map<String, dynamic>))
            .toList();
        return Result.success(alerts);
      }
      return Result.success([]);
    }

    return Result.failure(
      response.message ?? 'Failed to get alerts',
      code: response.code,
    );
  }

  /// Get alerts pending verification from the current user
  /// Requirements: 3.1 - Multi-person verification (2-of-3 Inner Circle)
  Future<Result<List<AlertWithVerifications>>> getPendingVerificationAlerts() async {
    final response = await apiService.get<Map<String, dynamic>>(
      '/alerts/pending-verification',
    );

    if (response.success && response.data != null) {
      final dataList = response.data!['data'] as List<dynamic>?;
      if (dataList != null) {
        final alerts = dataList
            .map((json) =>
                AlertWithVerifications.fromJson(json as Map<String, dynamic>))
            .toList();
        return Result.success(alerts);
      }
      return Result.success([]);
    }

    return Result.failure(
      response.message ?? 'Failed to get pending alerts',
      code: response.code,
    );
  }

  /// Get a specific alert by ID
  Future<Result<AlertWithVerifications>> getAlert(String alertId) async {
    final response = await apiService.get<Map<String, dynamic>>(
      '/alerts/$alertId',
    );

    if (response.success && response.data != null) {
      final alertData = response.data!['data'] as Map<String, dynamic>?;
      if (alertData != null) {
        return Result.success(AlertWithVerifications.fromJson(alertData));
      }
    }

    return Result.failure(
      response.message ?? 'Failed to get alert',
      code: response.code,
    );
  }


  /// Verify an alert (2-of-3 Inner Circle requirement)
  /// Requirements: 3.1 - Multi-person verification (2-of-3 Inner Circle)
  /// Requirements: 3.2 - Notify Inner Circle immediately via encrypted channels
  Future<Result<AlertVerification>> verifyAlert(String alertId) async {
    final response = await apiService.post<Map<String, dynamic>>(
      '/alerts/$alertId/verify',
    );

    if (response.success && response.data != null) {
      final verificationData = response.data!['data'] as Map<String, dynamic>?;
      if (verificationData != null) {
        return Result.success(AlertVerification.fromJson(verificationData));
      }
    }

    return Result.failure(
      response.message ?? 'Failed to verify alert',
      code: response.code,
    );
  }

  /// Force escalate an alert to the next level
  /// Requirements: 3.3 - Escalate to Community Circle after 30 minutes
  /// Requirements: 3.4 - Escalate to Professional Circle after 2 hours
  Future<Result<EscalationInfo>> escalateAlert(String alertId) async {
    final response = await apiService.post<Map<String, dynamic>>(
      '/alerts/$alertId/escalate',
    );

    if (response.success && response.data != null) {
      final escalationData = response.data!['data'] as Map<String, dynamic>?;
      if (escalationData != null) {
        return Result.success(EscalationInfo.fromJson(escalationData));
      }
    }

    return Result.failure(
      response.message ?? 'Failed to escalate alert',
      code: response.code,
    );
  }

  /// Resolve an alert and notify all participants
  /// Requirements: 3.5 - Notify all active participants and close the case
  Future<Result<AlertWithVerifications>> resolveAlert({
    required String alertId,
    String? resolutionNotesEncrypted,
  }) async {
    final response = await apiService.post<Map<String, dynamic>>(
      '/alerts/$alertId/resolve',
      data: resolutionNotesEncrypted != null
          ? {'resolution_notes_encrypted': resolutionNotesEncrypted}
          : null,
    );

    if (response.success && response.data != null) {
      final alertData = response.data!['data'] as Map<String, dynamic>?;
      if (alertData != null) {
        return Result.success(AlertWithVerifications.fromJson(alertData));
      }
    }

    return Result.failure(
      response.message ?? 'Failed to resolve alert',
      code: response.code,
    );
  }
}
