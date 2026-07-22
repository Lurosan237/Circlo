import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'realtime_service.dart';
import 'security_service.dart';
import '../../features/alerts/data/alert_repository.dart';
import '../../features/realtime/data/message_repository.dart';
import '../models/alert.dart';
import 'app_integration_service.dart';

/// Alert flow state for tracking the complete alert lifecycle
class AlertFlowState {
  final AlertWithVerifications? currentAlert;
  final List<Message> messages;
  final bool isLoading;
  final String? error;
  final AlertFlowPhase phase;

  const AlertFlowState({
    this.currentAlert,
    this.messages = const [],
    this.isLoading = false,
    this.error,
    this.phase = AlertFlowPhase.idle,
  });

  AlertFlowState copyWith({
    AlertWithVerifications? currentAlert,
    List<Message>? messages,
    bool? isLoading,
    String? error,
    AlertFlowPhase? phase,
  }) {
    return AlertFlowState(
      currentAlert: currentAlert ?? this.currentAlert,
      messages: messages ?? this.messages,
      isLoading: isLoading ?? this.isLoading,
      error: error,
      phase: phase ?? this.phase,
    );
  }
}

/// Phases of the alert flow
enum AlertFlowPhase {
  idle,
  creating,
  pendingVerification,
  verified,
  escalatedToCommunity,
  escalatedToProfessional,
  resolved,
  error,
}

/// Service for managing the complete end-to-end alert flow
/// 
/// Requirements:
/// - 3.1: Multi-person verification (2-of-3 Inner Circle)
/// - 3.2: Notify Inner Circle immediately via encrypted channels
/// - 3.3: Escalate to Community Circle after 30 minutes
/// - 3.4: Escalate to Professional Circle after 2 hours
/// - 3.5: Notify all active participants and close the case
/// - 5.1, 5.2, 5.3: End-to-end encrypted communications
class AlertFlowService extends StateNotifier<AlertFlowState> {
  final AlertRepository _alertRepository;
  final MessageRepository _messageRepository;
  final RealtimeService _realtimeService;

  StreamSubscription<AlertUpdate>? _alertUpdateSubscription;
  StreamSubscription<ChatMessage>? _messageSubscription;
  Timer? _escalationTimer;

  AlertFlowService({
    required AlertRepository alertRepository,
    required MessageRepository messageRepository,
    required RealtimeService realtimeService,
  })  : _alertRepository = alertRepository,
        _messageRepository = messageRepository,
        _realtimeService = realtimeService,
        super(const AlertFlowState());

  /// Start a new alert flow
  /// Requirements: 3.1 - Multi-person verification requirement
  Future<void> startAlert(AlertType type) async {
    state = state.copyWith(
      isLoading: true,
      phase: AlertFlowPhase.creating,
      error: null,
    );

    final result = await _alertRepository.createAlert(type: type);

    result.onSuccess((alertWithVerifications) async {
      // Join the alert channel for real-time updates
      await _messageRepository.joinAlertChannel(alertWithVerifications.alert.id);

      // Subscribe to alert updates
      _subscribeToAlertUpdates(alertWithVerifications.alert.id);

      // Subscribe to messages
      _subscribeToMessages();

      // Start escalation timer
      _startEscalationTimer(alertWithVerifications.alert);

      state = state.copyWith(
        currentAlert: alertWithVerifications,
        isLoading: false,
        phase: AlertFlowPhase.pendingVerification,
      );
    });

    result.onFailure((error, code) {
      state = state.copyWith(
        isLoading: false,
        error: error,
        phase: AlertFlowPhase.error,
      );
    });
  }

  /// Load an existing alert
  Future<void> loadAlert(String alertId) async {
    state = state.copyWith(isLoading: true, error: null);

    final result = await _alertRepository.getAlert(alertId);

    result.onSuccess((alertWithVerifications) async {
      // Join the alert channel
      await _messageRepository.joinAlertChannel(alertId);

      // Load existing messages
      await _loadMessages(alertId);

      // Subscribe to updates
      _subscribeToAlertUpdates(alertId);
      _subscribeToMessages();

      // Determine current phase
      final phase = _determinePhase(alertWithVerifications.alert);

      // Start escalation timer if needed
      if (phase != AlertFlowPhase.resolved) {
        _startEscalationTimer(alertWithVerifications.alert);
      }

      state = state.copyWith(
        currentAlert: alertWithVerifications,
        isLoading: false,
        phase: phase,
      );
    });

    result.onFailure((error, code) {
      state = state.copyWith(
        isLoading: false,
        error: error,
        phase: AlertFlowPhase.error,
      );
    });
  }

  /// Verify an alert (for Inner Circle members)
  /// Requirements: 3.1 - 2-of-3 Inner Circle verification
  Future<void> verifyAlert() async {
    final alert = state.currentAlert;
    if (alert == null) return;

    state = state.copyWith(isLoading: true);

    final result = await _alertRepository.verifyAlert(alert.alert.id);

    result.onSuccess((verification) async {
      // Refresh alert data
      await _refreshAlert(alert.alert.id);
    });

    result.onFailure((error, code) {
      state = state.copyWith(
        isLoading: false,
        error: error,
      );
    });
  }

  /// Manually escalate the alert
  /// Requirements: 3.3, 3.4 - Time-based escalation
  Future<void> escalateAlert() async {
    final alert = state.currentAlert;
    if (alert == null) return;

    state = state.copyWith(isLoading: true);

    final result = await _alertRepository.escalateAlert(alert.alert.id);

    result.onSuccess((escalationInfo) async {
      // Refresh alert data
      await _refreshAlert(alert.alert.id);
    });

    result.onFailure((error, code) {
      state = state.copyWith(
        isLoading: false,
        error: error,
      );
    });
  }

  /// Resolve the alert
  /// Requirements: 3.5 - Notify all active participants and close the case
  Future<void> resolveAlert({String? resolutionNotes}) async {
    final alert = state.currentAlert;
    if (alert == null) return;

    state = state.copyWith(isLoading: true);

    // Encrypt resolution notes if provided
    String? encryptedNotes;
    if (resolutionNotes != null && resolutionNotes.isNotEmpty) {
      final encrypted = SecurityService.encryptData(
        resolutionNotes,
        keyId: 'alert:${alert.alert.id}',
      );
      encryptedNotes = encrypted.ciphertext;
    }

    final result = await _alertRepository.resolveAlert(
      alertId: alert.alert.id,
      resolutionNotesEncrypted: encryptedNotes,
    );

    result.onSuccess((resolvedAlert) {
      _cancelEscalationTimer();

      state = state.copyWith(
        currentAlert: resolvedAlert,
        isLoading: false,
        phase: AlertFlowPhase.resolved,
      );
    });

    result.onFailure((error, code) {
      state = state.copyWith(
        isLoading: false,
        error: error,
      );
    });
  }

  /// Send a message in the alert channel
  /// Requirements: 5.1, 5.2 - End-to-end encrypted communications
  Future<void> sendMessage(String content) async {
    final alert = state.currentAlert;
    if (alert == null) return;

    try {
      await _messageRepository.sendMessage(alert.alert.id, content);
    } catch (e) {
      state = state.copyWith(error: e.toString());
    }
  }

  /// Load messages for the current alert
  Future<void> _loadMessages(String alertId) async {
    try {
      final messages = await _messageRepository.getAlertMessages(alertId);
      state = state.copyWith(messages: messages);
    } catch (e) {
      // Non-critical error, don't update error state
    }
  }

  /// Refresh alert data
  Future<void> _refreshAlert(String alertId) async {
    final result = await _alertRepository.getAlert(alertId);

    result.onSuccess((alertWithVerifications) {
      final phase = _determinePhase(alertWithVerifications.alert);

      state = state.copyWith(
        currentAlert: alertWithVerifications,
        isLoading: false,
        phase: phase,
      );
    });
  }

  /// Subscribe to real-time alert updates
  void _subscribeToAlertUpdates(String alertId) {
    _alertUpdateSubscription?.cancel();
    _alertUpdateSubscription = _realtimeService.alertUpdates
        .where((update) => update.alertId == alertId)
        .listen((update) {
      _handleAlertUpdate(update);
    });
  }

  /// Subscribe to real-time messages
  void _subscribeToMessages() {
    _messageSubscription?.cancel();
    _messageSubscription = _messageRepository.messageStream.listen((chatMessage) {
      if (state.currentAlert != null &&
          chatMessage.alertId == state.currentAlert!.alert.id) {
        _handleNewMessage(chatMessage);
      }
    });
  }

  /// Handle incoming alert update
  void _handleAlertUpdate(AlertUpdate update) {
    // Refresh alert data when we receive an update
    if (state.currentAlert != null) {
      _refreshAlert(state.currentAlert!.alert.id);
    }
  }

  /// Handle incoming message
  void _handleNewMessage(ChatMessage chatMessage) {
    final message = Message(
      id: chatMessage.id,
      alertId: chatMessage.alertId,
      senderId: chatMessage.senderId,
      contentEncrypted: chatMessage.content, // Already decrypted by realtime service
      iv: '',
      createdAt: chatMessage.sentAt,
      daysUntilDeletion: 90,
    );

    state = state.copyWith(
      messages: [...state.messages, message],
    );
  }

  /// Determine the current phase based on alert status
  AlertFlowPhase _determinePhase(Alert alert) {
    switch (alert.status) {
      case AlertStatus.pending:
        return AlertFlowPhase.pendingVerification;
      case AlertStatus.verified:
        if (alert.escalationLevel == 1) {
          return AlertFlowPhase.verified;
        } else if (alert.escalationLevel == 2) {
          return AlertFlowPhase.escalatedToCommunity;
        } else {
          return AlertFlowPhase.escalatedToProfessional;
        }
      case AlertStatus.escalated:
        if (alert.escalationLevel == 2) {
          return AlertFlowPhase.escalatedToCommunity;
        } else {
          return AlertFlowPhase.escalatedToProfessional;
        }
      case AlertStatus.resolved:
        return AlertFlowPhase.resolved;
    }
  }

  /// Start escalation timer based on current alert state
  /// Requirements: 3.3 - 30 minutes to Community Circle
  /// Requirements: 3.4 - 2 hours to Professional Circle
  void _startEscalationTimer(Alert alert) {
    _cancelEscalationTimer();

    if (alert.status == AlertStatus.resolved) return;

    Duration? escalationDelay;

    if (alert.escalationLevel == 1) {
      // Escalate to Community Circle after 30 minutes
      final timeSinceCreation = DateTime.now().difference(alert.createdAt);
      final remainingTime = const Duration(minutes: 30) - timeSinceCreation;
      if (remainingTime.isNegative) {
        // Should already be escalated
        escalationDelay = Duration.zero;
      } else {
        escalationDelay = remainingTime;
      }
    } else if (alert.escalationLevel == 2) {
      // Escalate to Professional Circle after 2 hours total
      final timeSinceCreation = DateTime.now().difference(alert.createdAt);
      final remainingTime = const Duration(hours: 2) - timeSinceCreation;
      if (remainingTime.isNegative) {
        escalationDelay = Duration.zero;
      } else {
        escalationDelay = remainingTime;
      }
    }

    if (escalationDelay != null) {
      _escalationTimer = Timer(escalationDelay, () {
        escalateAlert();
      });
    }
  }

  /// Cancel escalation timer
  void _cancelEscalationTimer() {
    _escalationTimer?.cancel();
    _escalationTimer = null;
  }

  /// Leave the current alert
  void leaveAlert() {
    if (state.currentAlert != null) {
      _messageRepository.leaveAlertChannel(state.currentAlert!.alert.id);
    }
    _alertUpdateSubscription?.cancel();
    _messageSubscription?.cancel();
    _cancelEscalationTimer();

    state = const AlertFlowState();
  }

  @override
  void dispose() {
    leaveAlert();
    super.dispose();
  }
}

/// Alert flow service provider
final alertFlowServiceProvider =
    StateNotifierProvider<AlertFlowService, AlertFlowState>((ref) {
  final alertRepository = ref.watch(alertRepositoryProvider);
  final messageRepository = ref.watch(messageRepositoryProvider);
  final realtimeService = ref.watch(realtimeServiceProvider);

  return AlertFlowService(
    alertRepository: alertRepository,
    messageRepository: messageRepository,
    realtimeService: realtimeService,
  );
});
