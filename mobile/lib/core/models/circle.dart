import 'package:freezed_annotation/freezed_annotation.dart';

part 'circle.freezed.dart';
part 'circle.g.dart';

/// Circle type enum representing the three trust levels
enum CircleType {
  @JsonValue('inner')
  inner,
  @JsonValue('community')
  community,
  @JsonValue('professional')
  professional,
}

/// Extension to get max members for each circle type
extension CircleTypeExtension on CircleType {
  int get maxMembers {
    switch (this) {
      case CircleType.inner:
        return 5;
      case CircleType.community:
        return 30;
      case CircleType.professional:
        return 50;
    }
  }

  int get minMembers {
    switch (this) {
      case CircleType.inner:
        return 3;
      case CircleType.community:
        return 15;
      case CircleType.professional:
        return 1;
    }
  }

  String get displayName {
    switch (this) {
      case CircleType.inner:
        return 'Inner Circle';
      case CircleType.community:
        return 'Community Circle';
      case CircleType.professional:
        return 'Professional Circle';
    }
  }
}

/// Member status in a circle
enum MemberStatus {
  @JsonValue('pending')
  pending,
  @JsonValue('active')
  active,
  @JsonValue('removed')
  removed,
}

/// Circle member model
@freezed
class CircleMember with _$CircleMember {
  const factory CircleMember({
    required String id,
    required String userId,
    required MemberStatus status,
    required DateTime invitedAt,
    DateTime? verifiedAt,
    @Default(false) bool mutualVerified,
  }) = _CircleMember;

  factory CircleMember.fromJson(Map<String, dynamic> json) =>
      _$CircleMemberFromJson(json);
}

/// Circle model
@freezed
class Circle with _$Circle {
  const factory Circle({
    required String id,
    required String ownerId,
    required CircleType type,
    required String nameEncrypted,
    required List<CircleMember> members,
    required int maxMembers,
    required DateTime createdAt,
  }) = _Circle;

  factory Circle.fromJson(Map<String, dynamic> json) => _$CircleFromJson(json);
}
