import 'package:freezed_annotation/freezed_annotation.dart';

part 'alert.freezed.dart';
part 'alert.g.dart';

/// Alert type enum
enum AlertType {
  @JsonValue('missing')
  missing,
  @JsonValue('emergency')
  emergency,
  @JsonValue('check_in')
  checkIn,
}

/// Alert status enum
enum AlertStatus {
  @JsonValue('pending')
  pending,
  @JsonValue('verified')
  verified,
  @JsonValue('escalated')
  escalated,
  @JsonValue('resolved')
  resolved,
}

/// Extension for alert status display
extension AlertStatusExtension on AlertStatus {
  String get displayName {
    switch (this) {
      case AlertStatus.pending:
        return 'Pending Verification';
      case AlertStatus.verified:
        return 'Verified';
      case AlertStatus.escalated:
        return 'Escalated';
      case AlertStatus.resolved:
        return 'Resolved';
    }
  }
}

/// Alert model
@freezed
class Alert with _$Alert {
  const factory Alert({
    required String id,
    required String userId,
    required AlertType type,
    required AlertStatus status,
    required int verificationCount,
    required int requiredVerifications,
    required int escalationLevel,
    required DateTime createdAt,
    DateTime? escalatedAt,
    DateTime? resolvedAt,
  }) = _Alert;

  factory Alert.fromJson(Map<String, dynamic> json) => _$AlertFromJson(json);
}

/// Alert verification model
@freezed
class AlertVerification with _$AlertVerification {
  const factory AlertVerification({
    required String id,
    required String alertId,
    required String verifierId,
    required DateTime verifiedAt,
  }) = _AlertVerification;

  factory AlertVerification.fromJson(Map<String, dynamic> json) =>
      _$AlertVerificationFromJson(json);
}
