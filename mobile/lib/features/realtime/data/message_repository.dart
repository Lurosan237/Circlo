import 'dart:async';
import '../../../core/services/api_service.dart';
import '../../../core/services/realtime_service.dart';
import '../../../core/services/security_service.dart';

/// Message model for encrypted communications
class Message {
  final String id;
  final String alertId;
  final String senderId;
  final String contentEncrypted;
  final String iv;
  final DateTime createdAt;
  final int daysUntilDeletion;

  Message({
    required this.id,
    required this.alertId,
    required this.senderId,
    required this.contentEncrypted,
    required this.iv,
    required this.createdAt,
    required this.daysUntilDeletion,
  });

  factory Message.fromJson(Map<String, dynamic> json) => Message(
    id: json['id'] as String,
    alertId: json['alert_id'] as String,
    senderId: json['sender_id'] as String,
    contentEncrypted: json['content_encrypted'] as String,
    iv: json['iv'] as String,
    createdAt: DateTime.parse(json['created_at'] as String),
    daysUntilDeletion: json['days_until_deletion'] as int,
  );

  /// Decrypt the message content locally
  /// Requirements: 5.3 - Decrypt content locally on the device
  String decryptContent() {
    final encryptedData = EncryptedData(
      ciphertext: contentEncrypted,
      iv: iv,
      keyId: 'alert:$alertId',
    );
    return SecurityService.decryptData(encryptedData);
  }
}

/// Repository for message operations
/// Requirements: 5.1, 5.2, 5.3, 5.4
class MessageRepository {
  final ApiService _apiService;
  final RealtimeService _realtimeService;

  MessageRepository({
    required ApiService apiService,
    required RealtimeService realtimeService,
  })  : _apiService = apiService,
        _realtimeService = realtimeService;

  /// Get messages for an alert
  Future<List<Message>> getAlertMessages(
    String alertId, {
    int limit = 100,
    int offset = 0,
  }) async {
    final response = await _apiService.get<Map<String, dynamic>>(
      '/messages/$alertId',
      queryParameters: {
        'limit': limit,
        'offset': offset,
      },
    );

    if (!response.success || response.data == null) {
      throw Exception(response.message ?? 'Failed to fetch messages');
    }

    final messagesJson = response.data!['messages'] as List<dynamic>? ?? [];
    return messagesJson
        .map((json) => Message.fromJson(json as Map<String, dynamic>))
        .toList();
  }

  /// Send a message to an alert channel
  /// Requirements: 5.1, 5.2 - End-to-end encrypted channels
  Future<void> sendMessage(String alertId, String content) async {
    // Send via API for persistence
    final response = await _apiService.post(
      '/messages',
      data: {
        'alert_id': alertId,
        'content': content,
      },
    );

    if (!response.success) {
      throw Exception(response.message ?? 'Failed to send message');
    }

    // Also send via Socket.io for real-time delivery
    await _realtimeService.sendMessage(alertId, content);
  }

  /// Join an alert channel for real-time updates
  Future<void> joinAlertChannel(String alertId) async {
    await _realtimeService.joinAlert(alertId);
  }

  /// Leave an alert channel
  void leaveAlertChannel(String alertId) {
    _realtimeService.leaveAlert(alertId);
  }

  /// Get stream of incoming messages
  Stream<ChatMessage> get messageStream => _realtimeService.messages;

  /// Get stream of alert updates
  Stream<AlertUpdate> get alertUpdateStream => _realtimeService.alertUpdates;

  /// Get connection state stream
  Stream<ConnectionState> get connectionStateStream =>
      _realtimeService.connectionState;

  /// Check if connected
  bool get isConnected => _realtimeService.isConnected;
}
