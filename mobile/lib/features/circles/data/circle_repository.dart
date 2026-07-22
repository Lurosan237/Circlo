import '../../../core/base/base_repository.dart';
import '../../../core/services/api_service.dart';
import '../../../core/models/circle.dart';

/// Pending invitation model
class PendingInvitation {
  final String circleId;
  final String circleNameEncrypted;
  final CircleType circleType;
  final String ownerId;
  final DateTime invitedAt;

  PendingInvitation({
    required this.circleId,
    required this.circleNameEncrypted,
    required this.circleType,
    required this.ownerId,
    required this.invitedAt,
  });

  factory PendingInvitation.fromJson(Map<String, dynamic> json) {
    return PendingInvitation(
      circleId: json['circle_id'] as String,
      circleNameEncrypted: json['circle_name_encrypted'] as String,
      circleType: CircleType.values.firstWhere(
        (e) => e.name == json['circle_type'],
        orElse: () => CircleType.inner,
      ),
      ownerId: json['owner_id'] as String,
      invitedAt: DateTime.parse(json['invited_at'] as String),
    );
  }
}

/// Repository for circle management operations
/// Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
class CircleRepository extends BaseRepository {
  CircleRepository({required super.apiService});

  /// Get all circles for the current user (owned and member of)
  /// Requirements: 2.5 - Role-based permissions
  Future<Result<List<Circle>>> getCircles() async {
    final response = await apiService.get<Map<String, dynamic>>(
      '/circles',
    );

    if (response.success && response.data != null) {
      final dataList = response.data!['data'] as List<dynamic>?;
      if (dataList != null) {
        final circles = dataList
            .map((json) => Circle.fromJson(json as Map<String, dynamic>))
            .toList();
        return Result.success(circles);
      }
      return Result.success([]);
    }

    return Result.failure(
      response.message ?? 'Failed to get circles',
      code: response.code,
    );
  }

  /// Get circles owned by the current user
  Future<Result<List<Circle>>> getOwnedCircles() async {
    final response = await apiService.get<Map<String, dynamic>>(
      '/circles/owned',
    );

    if (response.success && response.data != null) {
      final dataList = response.data!['data'] as List<dynamic>?;
      if (dataList != null) {
        final circles = dataList
            .map((json) => Circle.fromJson(json as Map<String, dynamic>))
            .toList();
        return Result.success(circles);
      }
      return Result.success([]);
    }

    return Result.failure(
      response.message ?? 'Failed to get owned circles',
      code: response.code,
    );
  }

  /// Get circles where user is a member (not owner)
  Future<Result<List<Circle>>> getMemberCircles() async {
    final response = await apiService.get<Map<String, dynamic>>(
      '/circles/member',
    );

    if (response.success && response.data != null) {
      final dataList = response.data!['data'] as List<dynamic>?;
      if (dataList != null) {
        final circles = dataList
            .map((json) => Circle.fromJson(json as Map<String, dynamic>))
            .toList();
        return Result.success(circles);
      }
      return Result.success([]);
    }

    return Result.failure(
      response.message ?? 'Failed to get member circles',
      code: response.code,
    );
  }

  /// Get pending invitations for the current user
  /// Requirements: 2.4 - Mutual verification requirement
  Future<Result<List<PendingInvitation>>> getPendingInvitations() async {
    final response = await apiService.get<Map<String, dynamic>>(
      '/circles/invitations',
    );

    if (response.success && response.data != null) {
      final dataList = response.data!['data'] as List<dynamic>?;
      if (dataList != null) {
        final invitations = dataList
            .map((json) => PendingInvitation.fromJson(json as Map<String, dynamic>))
            .toList();
        return Result.success(invitations);
      }
      return Result.success([]);
    }

    return Result.failure(
      response.message ?? 'Failed to get invitations',
      code: response.code,
    );
  }

  /// Create a new circle with size limit enforcement
  /// Requirements: 2.1 - Inner Circle: 3-5 members
  /// Requirements: 2.2 - Community Circle: 15-30 members
  /// Requirements: 2.3 - Professional Circle: verified resources
  Future<Result<Circle>> createCircle({
    required CircleType type,
    required String nameEncrypted,
    required int maxMembers,
  }) async {
    final response = await apiService.post<Map<String, dynamic>>(
      '/circles',
      data: {
        'type': type.name,
        'name_encrypted': nameEncrypted,
        'max_members': maxMembers,
      },
    );

    if (response.success && response.data != null) {
      final circleData = response.data!['data'] as Map<String, dynamic>?;
      if (circleData != null) {
        return Result.success(Circle.fromJson(circleData));
      }
    }

    return Result.failure(
      response.message ?? 'Failed to create circle',
      code: response.code,
    );
  }

  /// Get a specific circle by ID
  /// Requirements: 2.5 - Role-based permissions
  /// Requirements: 2.6 - Access revocation check
  Future<Result<Circle>> getCircle(String circleId) async {
    final response = await apiService.get<Map<String, dynamic>>(
      '/circles/$circleId',
    );

    if (response.success && response.data != null) {
      final circleData = response.data!['data'] as Map<String, dynamic>?;
      if (circleData != null) {
        return Result.success(Circle.fromJson(circleData));
      }
    }

    return Result.failure(
      response.message ?? 'Failed to get circle',
      code: response.code,
    );
  }

  /// Delete a circle (owner only)
  /// Requirements: 2.5 - Role-based permissions
  Future<Result<void>> deleteCircle(String circleId) async {
    final response = await apiService.delete<Map<String, dynamic>>(
      '/circles/$circleId',
    );

    if (response.success) {
      return Result.success(null);
    }

    return Result.failure(
      response.message ?? 'Failed to delete circle',
      code: response.code,
    );
  }

  /// Add a member to a circle (creates pending invitation)
  /// Requirements: 2.4 - Mutual verification before activation
  Future<Result<CircleMember>> addMember({
    required String circleId,
    required String userId,
  }) async {
    final response = await apiService.post<Map<String, dynamic>>(
      '/circles/$circleId/members',
      data: {'user_id': userId},
    );

    if (response.success && response.data != null) {
      final memberData = response.data!['data'] as Map<String, dynamic>?;
      if (memberData != null) {
        return Result.success(CircleMember.fromJson(memberData));
      }
    }

    return Result.failure(
      response.message ?? 'Failed to add member',
      code: response.code,
    );
  }

  /// Verify membership (accept invitation)
  /// Requirements: 2.4 - Mutual verification before activation
  Future<Result<CircleMember>> verifyMembership(String circleId) async {
    final response = await apiService.post<Map<String, dynamic>>(
      '/circles/$circleId/verify',
    );

    if (response.success && response.data != null) {
      final memberData = response.data!['data'] as Map<String, dynamic>?;
      if (memberData != null) {
        return Result.success(CircleMember.fromJson(memberData));
      }
    }

    return Result.failure(
      response.message ?? 'Failed to verify membership',
      code: response.code,
    );
  }

  /// Remove a member from a circle
  /// Requirements: 2.6 - Immediate access revocation on removal
  Future<Result<void>> removeMember({
    required String circleId,
    required String userId,
  }) async {
    final response = await apiService.delete<Map<String, dynamic>>(
      '/circles/$circleId/members/$userId',
    );

    if (response.success) {
      return Result.success(null);
    }

    return Result.failure(
      response.message ?? 'Failed to remove member',
      code: response.code,
    );
  }

  /// Leave a circle (remove self)
  /// Requirements: 2.6 - Immediate access revocation
  Future<Result<void>> leaveCircle(String circleId) async {
    final response = await apiService.post<Map<String, dynamic>>(
      '/circles/$circleId/leave',
    );

    if (response.success) {
      return Result.success(null);
    }

    return Result.failure(
      response.message ?? 'Failed to leave circle',
      code: response.code,
    );
  }
}
