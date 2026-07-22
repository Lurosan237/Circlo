/// Notification models for the Circlo safety app
/// 
/// Requirements: 8.1, 8.2, 8.3
/// - Push notifications via Firebase Cloud Messaging
/// - Encrypted notification payloads
/// - Priority-based notifications by circle type

/// Notification priority levels based on circle type
enum NotificationPriority {
  critical, // Inner Circle - highest priority
  high,     // Community Circle
  normal,   // Professional Circle
  low,      // General notifications
}

/// Notification delivery status
enum NotificationStatus {
  pending,   // Queued for delivery
  sent,      // Successfully sent to FCM
  delivered, // Confirmed delivered to device
  failed,    // Delivery failed
  expired,   // Notification expired before delivery
}

/// Types of notifications
enum NotificationType {
  alertCreated,
  alertVerified,
  alertEscalated,
  alertResolved,
  verificationRequest,
  checkRequest,
  circleInvite,
  circleUpdate,
  message,
  system,
}

/// Encrypted notification payload from FCM
class EncryptedNotificationPayload {
  final bool encrypted;
  final String payload;
  final String iv;
  final String notificationId;
  final String type;
  final String priority;
  final String timestamp;

  EncryptedNotificationPayload({
    required this.encrypted,
    required this.payload,
    required this.iv,
    required this.notificationId,
    required this.type,
    required this.priority,
    required this.timestamp,
  });

  factory EncryptedNotificationPayload.fromJson(Map<String, dynamic> json) {
    return EncryptedNotificationPayload(
      encrypted: json['encrypted'] as bool? ?? true,
      payload: json['payload'] as String,
      iv: json['iv'] as String,
      notificationId: json['notification_id'] as String,
      type: json['type'] as String,
      priority: json['priority'] as String,
      timestamp: json['timestamp'] as String,
    );
  }

  Map<String, dynamic> toJson() => {
    'encrypted': encrypted,
    'payload': payload,
    'iv': iv,
    'notification_id': notificationId,
    'type': type,
    'priority': priority,
    'timestamp': timestamp,
  };
}


/// Decrypted notification content
class NotificationContent {
  final String notificationId;
  final NotificationType type;
  final String title;
  final String body;
  final Map<String, dynamic>? data;
  final String? alertId;
  final String? circleId;
  final DateTime createdAt;

  NotificationContent({
    required this.notificationId,
    required this.type,
    required this.title,
    required this.body,
    this.data,
    this.alertId,
    this.circleId,
    required this.createdAt,
  });

  factory NotificationContent.fromJson(Map<String, dynamic> json) {
    return NotificationContent(
      notificationId: json['notification_id'] as String,
      type: _parseNotificationType(json['type'] as String),
      title: json['title'] as String,
      body: json['body'] as String,
      data: json['data'] as Map<String, dynamic>?,
      alertId: json['alert_id'] as String?,
      circleId: json['circle_id'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
    'notification_id': notificationId,
    'type': type.name,
    'title': title,
    'body': body,
    'data': data,
    'alert_id': alertId,
    'circle_id': circleId,
    'created_at': createdAt.toIso8601String(),
  };

  static NotificationType _parseNotificationType(String type) {
    switch (type) {
      case 'alert_created':
        return NotificationType.alertCreated;
      case 'alert_verified':
        return NotificationType.alertVerified;
      case 'alert_escalated':
        return NotificationType.alertEscalated;
      case 'alert_resolved':
        return NotificationType.alertResolved;
      case 'verification_request':
        return NotificationType.verificationRequest;
      case 'check_request':
        return NotificationType.checkRequest;
      case 'circle_invite':
        return NotificationType.circleInvite;
      case 'circle_update':
        return NotificationType.circleUpdate;
      case 'message':
        return NotificationType.message;
      default:
        return NotificationType.system;
    }
  }
}

/// User notification preferences
class NotificationPreferences {
  final String id;
  final String userId;
  final bool innerCircleEnabled;
  final bool communityCircleEnabled;
  final bool professionalCircleEnabled;
  final bool alertNotifications;
  final bool messageNotifications;
  final bool circleNotifications;
  final bool systemNotifications;
  final bool quietHoursEnabled;
  final String? quietHoursStart;
  final String? quietHoursEnd;

  NotificationPreferences({
    required this.id,
    required this.userId,
    this.innerCircleEnabled = true,
    this.communityCircleEnabled = true,
    this.professionalCircleEnabled = true,
    this.alertNotifications = true,
    this.messageNotifications = true,
    this.circleNotifications = true,
    this.systemNotifications = true,
    this.quietHoursEnabled = false,
    this.quietHoursStart,
    this.quietHoursEnd,
  });

  factory NotificationPreferences.fromJson(Map<String, dynamic> json) {
    return NotificationPreferences(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      innerCircleEnabled: json['inner_circle_enabled'] as bool? ?? true,
      communityCircleEnabled: json['community_circle_enabled'] as bool? ?? true,
      professionalCircleEnabled: json['professional_circle_enabled'] as bool? ?? true,
      alertNotifications: json['alert_notifications'] as bool? ?? true,
      messageNotifications: json['message_notifications'] as bool? ?? true,
      circleNotifications: json['circle_notifications'] as bool? ?? true,
      systemNotifications: json['system_notifications'] as bool? ?? true,
      quietHoursEnabled: json['quiet_hours_enabled'] as bool? ?? false,
      quietHoursStart: json['quiet_hours_start'] as String?,
      quietHoursEnd: json['quiet_hours_end'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'user_id': userId,
    'inner_circle_enabled': innerCircleEnabled,
    'community_circle_enabled': communityCircleEnabled,
    'professional_circle_enabled': professionalCircleEnabled,
    'alert_notifications': alertNotifications,
    'message_notifications': messageNotifications,
    'circle_notifications': circleNotifications,
    'system_notifications': systemNotifications,
    'quiet_hours_enabled': quietHoursEnabled,
    'quiet_hours_start': quietHoursStart,
    'quiet_hours_end': quietHoursEnd,
  };

  NotificationPreferences copyWith({
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
  }) {
    return NotificationPreferences(
      id: id,
      userId: userId,
      innerCircleEnabled: innerCircleEnabled ?? this.innerCircleEnabled,
      communityCircleEnabled: communityCircleEnabled ?? this.communityCircleEnabled,
      professionalCircleEnabled: professionalCircleEnabled ?? this.professionalCircleEnabled,
      alertNotifications: alertNotifications ?? this.alertNotifications,
      messageNotifications: messageNotifications ?? this.messageNotifications,
      circleNotifications: circleNotifications ?? this.circleNotifications,
      systemNotifications: systemNotifications ?? this.systemNotifications,
      quietHoursEnabled: quietHoursEnabled ?? this.quietHoursEnabled,
      quietHoursStart: quietHoursStart ?? this.quietHoursStart,
      quietHoursEnd: quietHoursEnd ?? this.quietHoursEnd,
    );
  }
}
