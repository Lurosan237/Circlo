import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/services/realtime_service.dart';
import '../../data/message_repository.dart';

/// State for the realtime controller
class RealtimeState {
  final ConnectionState connectionState;
  final List<ChatMessage> messages;
  final String? currentAlertId;
  final String? error;
  final bool isLoading;

  const RealtimeState({
    this.connectionState = ConnectionState.disconnected,
    this.messages = const [],
    this.currentAlertId,
    this.error,
    this.isLoading = false,
  });

  RealtimeState copyWith({
    ConnectionState? connectionState,
    List<ChatMessage>? messages,
    String? currentAlertId,
    String? error,
    bool? isLoading,
  }) {
    return RealtimeState(
      connectionState: connectionState ?? this.connectionState,
      messages: messages ?? this.messages,
      currentAlertId: currentAlertId ?? this.currentAlertId,
      error: error,
      isLoading: isLoading ?? this.isLoading,
    );
  }
}

/// Controller for real-time communication
/// 
/// Requirements: 5.1, 5.2, 5.3, 5.4
/// - Implement Socket.io client with encryption support
/// - Create encrypted message handling for active alerts
/// - Add real-time UI updates for alert status changes
/// - Implement local message decryption
class RealtimeController extends StateNotifier<RealtimeState> {
  final MessageRepository _repository;
  final RealtimeService _realtimeService;
  
  StreamSubscription<ConnectionState>? _connectionSubscription;
  StreamSubscription<ChatMessage>? _messageSubscription;
  StreamSubscription<AlertUpdate>? _alertUpdateSubscription;
  StreamSubscription<String>? _errorSubscription;

  // Callbacks for alert updates
  void Function(AlertUpdate)? onAlertUpdate;

  RealtimeController({
    required MessageRepository repository,
    required RealtimeService realtimeService,
  })  : _repository = repository,
        _realtimeService = realtimeService,
        super(const RealtimeState()) {
    _setupSubscriptions();
  }

  void _setupSubscriptions() {
    _connectionSubscription = _realtimeService.connectionState.listen((state) {
      this.state = this.state.copyWith(connectionState: state);
    });

    _messageSubscription = _realtimeService.messages.listen((message) {
      // Add new message to the list if it's for the current alert
      if (message.alertId == state.currentAlertId) {
        final updatedMessages = [...state.messages, message];
        this.state = this.state.copyWith(messages: updatedMessages);
      }
    });

    _alertUpdateSubscription = _realtimeService.alertUpdates.listen((update) {
      // Notify listeners about alert updates
      onAlertUpdate?.call(update);
    });

    _errorSubscription = _realtimeService.errors.listen((error) {
      this.state = this.state.copyWith(error: error);
    });
  }

  /// Connect to the realtime server
  Future<void> connect() async {
    state = state.copyWith(isLoading: true, error: null);
    
    try {
      final success = await _realtimeService.connect();
      if (!success) {
        state = state.copyWith(
          error: 'Failed to connect to server',
          isLoading: false,
        );
      } else {
        state = state.copyWith(isLoading: false);
      }
    } catch (e) {
      state = state.copyWith(
        error: 'Connection error: $e',
        isLoading: false,
      );
    }
  }

  /// Join an alert channel for real-time updates
  Future<void> joinAlert(String alertId) async {
    state = state.copyWith(
      isLoading: true,
      currentAlertId: alertId,
      messages: [],
      error: null,
    );

    try {
      // Ensure connected
      if (!_realtimeService.isConnected) {
        await connect();
      }

      // Join the alert channel
      await _repository.joinAlertChannel(alertId);

      // Load existing messages
      final messages = await _repository.getAlertMessages(alertId);
      
      // Convert to ChatMessage format
      final chatMessages = messages.map((m) => ChatMessage(
        id: m.id,
        alertId: m.alertId,
        senderId: m.senderId,
        content: m.decryptContent(),
        sentAt: m.createdAt,
      )).toList();

      state = state.copyWith(
        messages: chatMessages,
        isLoading: false,
      );
    } catch (e) {
      state = state.copyWith(
        error: 'Failed to join alert: $e',
        isLoading: false,
      );
    }
  }

  /// Leave the current alert channel
  void leaveAlert() {
    if (state.currentAlertId != null) {
      _repository.leaveAlertChannel(state.currentAlertId!);
      state = state.copyWith(
        currentAlertId: null,
        messages: [],
      );
    }
  }

  /// Send a message to the current alert channel
  /// Requirements: 5.1, 5.2 - Encrypt all content before transmission
  Future<void> sendMessage(String content) async {
    if (state.currentAlertId == null) {
      state = state.copyWith(error: 'No alert channel joined');
      return;
    }

    try {
      await _repository.sendMessage(state.currentAlertId!, content);
    } catch (e) {
      state = state.copyWith(error: 'Failed to send message: $e');
    }
  }

  /// Send an alert status update
  /// Requirements: 5.4 - Real-time updates via Socket.io with encrypted payloads
  Future<void> sendAlertUpdate(
    String status, {
    Map<String, dynamic>? data,
  }) async {
    if (state.currentAlertId == null) {
      state = state.copyWith(error: 'No alert channel joined');
      return;
    }

    try {
      await _realtimeService.sendAlertUpdate(
        state.currentAlertId!,
        status,
        data: data,
      );
    } catch (e) {
      state = state.copyWith(error: 'Failed to send update: $e');
    }
  }

  /// Clear any error
  void clearError() {
    state = state.copyWith(error: null);
  }

  /// Disconnect from the server
  void disconnect() {
    _realtimeService.disconnect();
    state = const RealtimeState();
  }

  @override
  void dispose() {
    _connectionSubscription?.cancel();
    _messageSubscription?.cancel();
    _alertUpdateSubscription?.cancel();
    _errorSubscription?.cancel();
    _realtimeService.dispose();
    super.dispose();
  }
}
