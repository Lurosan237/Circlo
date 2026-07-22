import 'dart:async';
import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../models/notification.dart';
import 'security_service.dart';

/// Notification service for handling FCM and encrypted notifications
/// 
/// Requirements: 8.1, 8.2, 8.5
/// - FCM client integration
/// - Notification decryption and display
/// - User notification preferences by circle type
class NotificationService {
  static const FlutterSecureStorage _secureStorage = FlutterSecureStorage();
  static const String _deviceTokenKey = 'fcm_device_token';
  static const String _preferencesKey = 'notification_preferences';
  
  // Stream controllers for notification events
  final _notificationController = StreamController<NotificationContent>.broadcast();
  Stream<NotificationContent> get notifications => _notificationController.stream;
  
  final _tokenRefreshController = StreamController<String>.broadcast();
  Stream<String> get tokenRefresh => _tokenRefreshController.stream;
  
  String? _currentToken;
  NotificationPreferences? _preferences;
  bool _initialized = false;

  /// Initialize the notification service
  Future<void> initialize() async {
    if (_initialized) return;
    
    // Load saved device token
    _currentToken = await _secureStorage.read(key: _deviceTokenKey);
    
    // Load saved preferences
    final prefsJson = await _secureStorage.read(key: _preferencesKey);
    if (prefsJson != null) {
      _preferences = NotificationPreferences.fromJson(
        jsonDecode(prefsJson) as Map<String, dynamic>,
      );
    }
    
    _initialized = true;
  }

  /// Get the current FCM device token
  String? get currentToken => _currentToken;

  /// Get current notification preferences
  NotificationPreferences? get preferences => _preferences;

  /// Save device token locally
  Future<void> saveDeviceToken(String token) async {
    _currentToken = token;
    await _secureStorage.write(key: _deviceTokenKey, value: token);
    _tokenRefreshController.add(token);
  }

  /// Clear device token (on logout)
  Future<void> clearDeviceToken() async {
    _currentToken = null;
    await _secureStorage.delete(key: _deviceTokenKey);
  }


  /// Decrypt an encrypted notification payload
  /// 
  /// Requirements: 8.2 - Encrypted notification payloads
  NotificationContent decryptNotification(EncryptedNotificationPayload payload) {
    try {
      // Decrypt the payload using the security service
      final encryptedData = EncryptedData(
        ciphertext: payload.payload,
        iv: payload.iv,
      );
      
      final decryptedJson = SecurityService.decryptData(encryptedData);
      final data = jsonDecode(decryptedJson) as Map<String, dynamic>;
      
      return NotificationContent.fromJson(data);
    } catch (e) {
      throw Exception('Failed to decrypt notification: $e');
    }
  }

  /// Handle incoming FCM notification
  /// 
  /// Requirements: 8.1 - Push notifications via Firebase Cloud Messaging
  Future<void> handleNotification(Map<String, dynamic> message) async {
    try {
      // Check if notification is encrypted
      if (message['encrypted'] == true || message['encrypted'] == 'true') {
        final payload = EncryptedNotificationPayload.fromJson(message);
        final content = decryptNotification(payload);
        
        // Check if notification should be shown based on preferences
        if (_shouldShowNotification(content)) {
          _notificationController.add(content);
        }
      } else {
        // Handle unencrypted notification (fallback)
        final content = NotificationContent(
          notificationId: message['notification_id'] as String? ?? '',
          type: NotificationType.system,
          title: message['title'] as String? ?? '',
          body: message['body'] as String? ?? '',
          data: message['data'] as Map<String, dynamic>?,
          createdAt: DateTime.now(),
        );
        
        if (_shouldShowNotification(content)) {
          _notificationController.add(content);
        }
      }
    } catch (e) {
      // Log error but don't crash
      print('Error handling notification: $e');
    }
  }

  /// Check if notification should be shown based on user preferences
  /// 
  /// Requirements: 8.5 - User notification preferences by circle type
  bool _shouldShowNotification(NotificationContent content) {
    if (_preferences == null) return true;
    
    // Check notification type preferences
    switch (content.type) {
      case NotificationType.alertCreated:
      case NotificationType.alertVerified:
      case NotificationType.alertEscalated:
      case NotificationType.alertResolved:
      case NotificationType.verificationRequest:
      case NotificationType.checkRequest:
        return _preferences!.alertNotifications;
      case NotificationType.message:
        return _preferences!.messageNotifications;
      case NotificationType.circleInvite:
      case NotificationType.circleUpdate:
        return _preferences!.circleNotifications;
      case NotificationType.system:
        return _preferences!.systemNotifications;
    }
  }

  /// Update notification preferences
  Future<void> updatePreferences(NotificationPreferences preferences) async {
    _preferences = preferences;
    await _secureStorage.write(
      key: _preferencesKey,
      value: jsonEncode(preferences.toJson()),
    );
  }

  /// Get notification priority for display
  /// 
  /// Requirements: 8.3 - Priority-based notifications by circle type
  static NotificationPriority getPriorityFromString(String priority) {
    switch (priority.toLowerCase()) {
      case 'critical':
        return NotificationPriority.critical;
      case 'high':
        return NotificationPriority.high;
      case 'normal':
        return NotificationPriority.normal;
      case 'low':
        return NotificationPriority.low;
      default:
        return NotificationPriority.normal;
    }
  }

  /// Check if notification is high priority (should show immediately)
  static bool isHighPriority(String priority) {
    final p = getPriorityFromString(priority);
    return p == NotificationPriority.critical || p == NotificationPriority.high;
  }

  /// Dispose of resources
  void dispose() {
    _notificationController.close();
    _tokenRefreshController.close();
  }
}
