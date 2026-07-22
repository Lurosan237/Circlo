import 'package:freezed_annotation/freezed_annotation.dart';

part 'user.freezed.dart';
part 'user.g.dart';

/// User model
@freezed
class User with _$User {
  const factory User({
    required String id,
    required String phoneHash,
    required String nameEncrypted,
    required DateTime createdAt,
    required DateTime lastActive,
  }) = _User;

  factory User.fromJson(Map<String, dynamic> json) => _$UserFromJson(json);
}

/// Authentication result model
@freezed
class AuthResult with _$AuthResult {
  const factory AuthResult({
    required String accessToken,
    String? refreshToken,
    required User user,
  }) = _AuthResult;

  factory AuthResult.fromJson(Map<String, dynamic> json) =>
      _$AuthResultFromJson(json);
}
