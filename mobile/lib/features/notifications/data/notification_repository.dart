import '../../../core/base/base_repository.dart';
import '../../../core/models/notification.dart';
import '../../../core/services/api_service.dart';

/// Repository for notification-related API operations
/// 
/// Requirements: 8.1, 8.2, 8.5
/// - FCM client integration
/// - Notification decryption and display
/// - User notification preferences by circle type
class NotificationRepository {
  final ApiService _apiService;

  NotificationRepository({required ApiService apiService})
      : _apiService = apiService;

  /// Register device token with the backend
  /// 
  /// Requirements: 8.1 - Push notifications via Firebase Cloud Messaging
  Future<Result<Map<String, dynamic>>> registerDeviceToken({
    required String token,
    required String platform,
  }) async {
    try {
      final response = await _apiService.post(
        '/notifications/device-token',
        data: {
          'token': token,
          'platform': platform,
        },
      );
      return Result.success(response.data as Map<String, dynamic>);
    } catch (e) {
      return Result.failure(e.toString());
    }
  }

  /// Unregister device token
  Future<Result<void>> unregisterDeviceToken(String token) async {
    try {
      await _apiService.delete('/notifications/device-token/$token');
      return Result.success(null);
    } catch (e) {
      return Result.failure(e.toString());
    }
  }

  /// Get all device tokens for the current user
  Future<Result<List<Map<String, dynamic>>>> getDeviceTokens() async {
    try {
      final response = await _apiService.get('/notifications/device-tokens');
      final data = response.data as Map<String, dynamic>;
      return Result.success((data['data'] as List).cast<Map<String, dynamic>>());
    } catch (e) {
      return Result.failure(e.toString());
    }
  }


  /// Get notification preferences
  /// 
  /// Requirements: 8.5 - User notification preferences by circle type
  Future<Result<NotificationPreferences>> getPreferences() async {
    try {
      final response = await _apiService.get('/notifications/preferences');
      final data = response.data as Map<String, dynamic>;
      return Result.success(NotificationPreferences.fromJson(data['data'] as Map<String, dynamic>));
    } catch (e) {
      return Result.failure(e.toString());
    }
  }

  /// Update notification preferences
  /// 
  /// Requirements: 8.5 - User notification preferences by circle type
  Future<Result<NotificationPreferences>> updatePreferences({
    bool? innerCircleEnabled,
    bool? communityCircleEnabled,
    bool? professionalCircleEnabled,
    bool? alertNotifications,
    bool? messageNotifications,
    bool? circleNotifications,
    bool? systemNotifications,
    bool? quietHoursEnabled,
    String? quietHoursStart,
    String? quietHoursEnd,
  }) async {
    try {
      final data = <String, dynamic>{};
      
      if (innerCircleEnabled != null) data['inner_circle_enabled'] = innerCircleEnabled;
      if (communityCircleEnabled != null) data['community_circle_enabled'] = communityCircleEnabled;
      if (professionalCircleEnabled != null) data['professional_circle_enabled'] = professionalCircleEnabled;
      if (alertNotifications != null) data['alert_notifications'] = alertNotifications;
      if (messageNotifications != null) data['message_notifications'] = messageNotifications;
      if (circleNotifications != null) data['circle_notifications'] = circleNotifications;
      if (systemNotifications != null) data['system_notifications'] = systemNotifications;
      if (quietHoursEnabled != null) data['quiet_hours_enabled'] = quietHoursEnabled;
      if (quietHoursStart != null) data['quiet_hours_start'] = quietHoursStart;
      if (quietHoursEnd != null) data['quiet_hours_end'] = quietHoursEnd;
      
      final response = await _apiService.put(
        '/notifications/preferences',
        data: data,
      );
      final responseData = response.data as Map<String, dynamic>;
      return Result.success(NotificationPreferences.fromJson(responseData['data'] as Map<String, dynamic>));
    } catch (e) {
      return Result.failure(e.toString());
    }
  }

  /// Get notifications with pagination
  Future<Result<NotificationListResult>> getNotifications({
    int page = 1,
    int pageSize = 20,
    bool includeContent = false,
  }) async {
    try {
      final response = await _apiService.get(
        '/notifications',
        queryParameters: {
          'page': page,
          'page_size': pageSize,
          'include_content': includeContent,
        },
      );
      final data = response.data as Map<String, dynamic>;
      final resultData = data['data'] as Map<String, dynamic>;
      
      return Result.success(NotificationListResult(
        notifications: (resultData['notifications'] as List)
            .map((n) => NotificationItem.fromJson(n as Map<String, dynamic>))
            .toList(),
        total: resultData['total'] as int,
        page: resultData['page'] as int,
        pageSize: resultData['page_size'] as int,
        hasMore: resultData['has_more'] as bool,
      ));
    } catch (e) {
      return Result.failure(e.toString());
    }
  }

  /// Mark notification as delivered
  Future<Result<void>> markAsDelivered(String notificationId) async {
    try {
      await _apiService.post('/notifications/$notificationId/delivered');
      return Result.success(null);
    } catch (e) {
      return Result.failure(e.toString());
    }
  }
}

/// Result for paginated notification list
class NotificationListResult {
  final List<NotificationItem> notifications;
  final int total;
  final int page;
  final int pageSize;
  final bool hasMore;

  NotificationListResult({
    required this.notifications,
    required this.total,
    required this.page,
    required this.pageSize,
    required this.hasMore,
  });
}

/// Notification item from API
class NotificationItem {
  final String id;
  final String userId;
  final String type;
  final String priority;
  final String status;
  final String? alertId;
  final String? circleId;
  final DateTime createdAt;
  final DateTime? sentAt;
  final DateTime? deliveredAt;
  final String? title;
  final String? body;
  final Map<String, dynamic>? data;

  NotificationItem({
    required this.id,
    required this.userId,
    required this.type,
    required this.priority,
    required this.status,
    this.alertId,
    this.circleId,
    required this.createdAt,
    this.sentAt,
    this.deliveredAt,
    this.title,
    this.body,
    this.data,
  });

  factory NotificationItem.fromJson(Map<String, dynamic> json) {
    return NotificationItem(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      type: json['type'] as String,
      priority: json['priority'] as String,
      status: json['status'] as String,
      alertId: json['alert_id'] as String?,
      circleId: json['circle_id'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
      sentAt: json['sent_at'] != null ? DateTime.parse(json['sent_at'] as String) : null,
      deliveredAt: json['delivered_at'] != null ? DateTime.parse(json['delivered_at'] as String) : null,
      title: json['title'] as String?,
      body: json['body'] as String?,
      data: json['data'] as Map<String, dynamic>?,
    );
  }
}
