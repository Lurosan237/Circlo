import 'dart:async';
import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:socket_io_client/socket_io_client.dart' as io;
import 'security_service.dart';

/// Encrypted message payload for Socket.io communication
class EncryptedPayload {
  final bool encrypted;
  final String payload;
  final String iv;
  final String timestamp;

  EncryptedPayload({
    required this.encrypted,
    required this.payload,
    required this.iv,
    required this.timestamp,
  });

  Map<String, dynamic> toJson() => {
    'encrypted': encrypted,
    'payload': payload,
    'iv': iv,
    'timestamp': timestamp,
  };

  factory EncryptedPayload.fromJson(Map<String, dynamic> json) => EncryptedPayload(
    encrypted: json['encrypted'] as bool,
    payload: json['payload'] as String,
    iv: json['iv'] as String,
    timestamp: json['timestamp'] as String,
  );
}

/// Chat message for alert communications
class ChatMessage {
  final String id;
  final String alertId;
  final String senderId;
  final String content;
  final DateTime sentAt;
  final bool isEncrypted;

  ChatMessage({
    required this.id,
    required this.alertId,
    required this.senderId,
    required this.content,
    required this.sentAt,
    this.isEncrypted = true,
  });

  Map<String, dynamic> toJson() => {
    'id': id,
    'alert_id': alertId,
    'sender_id': senderId,
    'content': content,
    'sent_at': sentAt.toIso8601String(),
    'is_encrypted': isEncrypted,
  };

  factory ChatMessage.fromJson(Map<String, dynamic> json) => ChatMessage(
    id: json['id'] as String? ?? '',
    alertId: json['alert_id'] as String,
    senderId: json['sender_id'] as String,
    content: json['content'] as String,
    sentAt: DateTime.parse(json['sent_at'] as String),
    isEncrypted: json['is_encrypted'] as bool? ?? true,
  );
}

/// Alert update for real-time status changes
class AlertUpdate {
  final String alertId;
  final String status;
  final Map<String, dynamic>? data;
  final DateTime timestamp;

  AlertUpdate({
    required this.alertId,
    required this.status,
    this.data,
    required this.timestamp,
  });

  factory AlertUpdate.fromJson(Map<String, dynamic> json) => AlertUpdate(
    alertId: json['alert_id'] as String,
    status: json['status'] as String,
    data: json['data'] as Map<String, dynamic>?,
    timestamp: DateTime.parse(json['timestamp'] as String? ?? DateTime.now().toIso8601String()),
  );
}

/// Connection state for the realtime service
enum ConnectionState {
  disconnected,
  connecting,
  connected,
  reconnecting,
  error,
}

/// Real-time communication service using Socket.io with encryption
/// 
/// Requirements: 5.1, 5.2, 5.3, 5.4
/// - Implement Socket.io client with encryption support
/// - Create encrypted message handling for active alerts
/// - Add real-time UI updates for alert status changes
/// - Implement local message decryption
class RealtimeService {
  static const String _tokenKey = 'auth_token';
  static const FlutterSecureStorage _secureStorage = FlutterSecureStorage();
  
  io.Socket? _socket;
  final String serverUrl;
  String? _currentUserId;
  
  // Connection state
  ConnectionState _connectionState = ConnectionState.disconnected;
  final _connectionStateController = StreamController<ConnectionState>.broadcast();
  Stream<ConnectionState> get connectionState => _connectionStateController.stream;
  
  // Message streams
  final _messageController = StreamController<ChatMessage>.broadcast();
  Stream<ChatMessage> get messages => _messageController.stream;
  
  // Alert update streams
  final _alertUpdateController = StreamController<AlertUpdate>.broadcast();
  Stream<AlertUpdate> get alertUpdates => _alertUpdateController.stream;
  
  // Error streams
  final _errorController = StreamController<String>.broadcast();
  Stream<String> get errors => _errorController.stream;
  
  // Joined alert rooms
  final Set<String> _joinedAlerts = {};

  RealtimeService({required this.serverUrl});

  /// Initialize and connect to the Socket.io server
  Future<bool> connect() async {
    if (_socket != null && _socket!.connected) {
      return true;
    }

    _updateConnectionState(ConnectionState.connecting);

    try {
      final token = await _secureStorage.read(key: _tokenKey);
      if (token == null) {
        _updateConnectionState(ConnectionState.error);
        _errorController.add('Authentication token not found');
        return false;
      }

      _socket = io.io(
        '$serverUrl/ws',
        io.OptionBuilder()
            .setTransports(['websocket'])
            .setAuth({'token': token})
            .enableAutoConnect()
            .enableReconnection()
            .setReconnectionAttempts(5)
            .setReconnectionDelay(1000)
            .build(),
      );

      _setupEventHandlers();
      _socket!.connect();

      return true;
    } catch (e) {
      _updateConnectionState(ConnectionState.error);
      _errorController.add('Connection failed: $e');
      return false;
    }
  }

  /// Set up Socket.io event handlers
  void _setupEventHandlers() {
    _socket!.onConnect((_) {
      _updateConnectionState(ConnectionState.connected);
      // Rejoin any previously joined alert rooms
      for (final alertId in _joinedAlerts) {
        _socket!.emit('join_alert', {'alert_id': alertId});
      }
    });

    _socket!.onDisconnect((_) {
      _updateConnectionState(ConnectionState.disconnected);
    });

    _socket!.onConnectError((error) {
      _updateConnectionState(ConnectionState.error);
      _errorController.add('Connection error: $error');
    });

    _socket!.onReconnecting((_) {
      _updateConnectionState(ConnectionState.reconnecting);
    });

    _socket!.on('connected', (data) {
      if (data is Map<String, dynamic>) {
        _currentUserId = data['user_id'] as String?;
      }
    });

    _socket!.on('error', (data) {
      if (data is Map<String, dynamic>) {
        _errorController.add(data['message'] as String? ?? 'Unknown error');
      }
    });

    _socket!.on('joined_alert', (data) {
      if (data is Map<String, dynamic>) {
        final alertId = data['alert_id'] as String?;
        if (alertId != null) {
          _joinedAlerts.add(alertId);
        }
      }
    });

    _socket!.on('left_alert', (data) {
      if (data is Map<String, dynamic>) {
        final alertId = data['alert_id'] as String?;
        if (alertId != null) {
          _joinedAlerts.remove(alertId);
        }
      }
    });

    // Handle incoming encrypted messages
    _socket!.on('message', (data) {
      _handleIncomingMessage(data);
    });

    // Handle alert updates
    _socket!.on('alert_update', (data) {
      _handleAlertUpdate(data);
    });
  }

  /// Handle incoming encrypted message
  void _handleIncomingMessage(dynamic data) {
    try {
      if (data is! Map<String, dynamic>) return;

      final alertId = data['alert_id'] as String?;
      final senderId = data['sender_id'] as String?;
      final payload = data['payload'];
      final timestamp = data['timestamp'] as String?;

      if (alertId == null || senderId == null || payload == null) return;

      // Decrypt the message payload
      String content;
      if (payload is Map<String, dynamic> && payload['encrypted'] == true) {
        content = _decryptPayload(payload, alertId);
      } else {
        content = payload['content'] as String? ?? '';
      }

      final message = ChatMessage(
        id: '${alertId}_${timestamp ?? DateTime.now().millisecondsSinceEpoch}',
        alertId: alertId,
        senderId: senderId,
        content: content,
        sentAt: timestamp != null ? DateTime.parse(timestamp) : DateTime.now(),
      );

      _messageController.add(message);
    } catch (e) {
      _errorController.add('Failed to process message: $e');
    }
  }

  /// Handle alert status update
  void _handleAlertUpdate(dynamic data) {
    try {
      if (data is! Map<String, dynamic>) return;

      final alertId = data['alert_id'] as String?;
      final payload = data['payload'];
      final timestamp = data['timestamp'] as String?;

      if (alertId == null || payload == null) return;

      // Decrypt the update payload if encrypted
      Map<String, dynamic> updateData;
      if (payload is Map<String, dynamic> && payload['encrypted'] == true) {
        final decrypted = _decryptPayload(payload, alertId);
        updateData = jsonDecode(decrypted) as Map<String, dynamic>;
      } else if (payload is Map<String, dynamic>) {
        updateData = payload;
      } else {
        return;
      }

      final update = AlertUpdate(
        alertId: alertId,
        status: updateData['status'] as String? ?? 'unknown',
        data: updateData['data'] as Map<String, dynamic>?,
        timestamp: timestamp != null ? DateTime.parse(timestamp) : DateTime.now(),
      );

      _alertUpdateController.add(update);
    } catch (e) {
      _errorController.add('Failed to process alert update: $e');
    }
  }

  /// Decrypt an encrypted payload
  /// Requirements: 5.3 - Decrypt content locally on the device
  String _decryptPayload(Map<String, dynamic> payload, String alertId) {
    try {
      final encryptedData = EncryptedData(
        ciphertext: payload['payload'] as String,
        iv: payload['iv'] as String,
        keyId: 'alert:$alertId',
      );
      return SecurityService.decryptData(encryptedData);
    } catch (e) {
      throw Exception('Decryption failed: $e');
    }
  }

  /// Encrypt a message payload
  /// Requirements: 5.1, 5.2 - End-to-end encrypted channels using AES-256-GCM
  EncryptedPayload _encryptPayload(Map<String, dynamic> message, String alertId) {
    final messageJson = jsonEncode(message);
    final encrypted = SecurityService.encryptData(messageJson, keyId: 'alert:$alertId');
    
    return EncryptedPayload(
      encrypted: true,
      payload: encrypted.ciphertext,
      iv: encrypted.iv,
      timestamp: DateTime.now().toUtc().toIso8601String(),
    );
  }

  /// Join an alert room for real-time updates
  Future<void> joinAlert(String alertId) async {
    if (_socket == null || !_socket!.connected) {
      await connect();
    }

    _socket?.emit('join_alert', {'alert_id': alertId});
    _joinedAlerts.add(alertId);
  }

  /// Leave an alert room
  void leaveAlert(String alertId) {
    _socket?.emit('leave_alert', {'alert_id': alertId});
    _joinedAlerts.remove(alertId);
  }

  /// Send an encrypted message to an alert channel
  /// Requirements: 5.1, 5.2 - Encrypt all content before transmission
  Future<void> sendMessage(String alertId, String content) async {
    if (_socket == null || !_socket!.connected) {
      throw Exception('Not connected to server');
    }

    if (_currentUserId == null) {
      throw Exception('User not authenticated');
    }

    final message = {
      'type': 'chat_message',
      'alert_id': alertId,
      'sender_id': _currentUserId,
      'content': content,
      'sent_at': DateTime.now().toUtc().toIso8601String(),
    };

    final encryptedPayload = _encryptPayload(message, alertId);

    _socket!.emit('send_message', {
      'alert_id': alertId,
      'payload': encryptedPayload.toJson(),
    });
  }

  /// Send an encrypted alert status update
  /// Requirements: 5.4 - Real-time updates via Socket.io with encrypted payloads
  Future<void> sendAlertUpdate(
    String alertId,
    String status, {
    Map<String, dynamic>? data,
  }) async {
    if (_socket == null || !_socket!.connected) {
      throw Exception('Not connected to server');
    }

    final update = {
      'type': 'alert_update',
      'alert_id': alertId,
      'status': status,
      'data': data ?? {},
    };

    final encryptedPayload = _encryptPayload(update, alertId);

    _socket!.emit('send_alert_update', {
      'alert_id': alertId,
      'payload': encryptedPayload.toJson(),
    });
  }

  /// Update connection state and notify listeners
  void _updateConnectionState(ConnectionState state) {
    _connectionState = state;
    _connectionStateController.add(state);
  }

  /// Get current connection state
  ConnectionState get currentConnectionState => _connectionState;

  /// Check if connected
  bool get isConnected => _socket?.connected ?? false;

  /// Get current user ID
  String? get currentUserId => _currentUserId;

  /// Get list of joined alert rooms
  Set<String> get joinedAlerts => Set.unmodifiable(_joinedAlerts);

  /// Disconnect from the server
  void disconnect() {
    _socket?.disconnect();
    _socket?.dispose();
    _socket = null;
    _joinedAlerts.clear();
    _currentUserId = null;
    _updateConnectionState(ConnectionState.disconnected);
  }

  /// Dispose of resources
  void dispose() {
    disconnect();
    _connectionStateController.close();
    _messageController.close();
    _alertUpdateController.close();
    _errorController.close();
  }
}
