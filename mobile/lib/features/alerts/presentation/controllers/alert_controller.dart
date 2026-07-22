import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/models/alert.dart';
import '../../../../core/services/api_service.dart';
import '../../data/alert_repository.dart';

/// Alert management state
class AlertState {
  final bool isLoading;
  final List<AlertWithVerifications> myAlerts;
  final List<AlertWithVerifications> pendingVerificationAlerts;
  final AlertWithVerifications? selectedAlert;
  final String? error;
  final String? errorCode;

  const AlertState({
    this.isLoading = false,
    this.myAlerts = const [],
    this.pendingVerificationAlerts = const [],
    this.selectedAlert,
    this.error,
    this.errorCode,
  });

  AlertState copyWith({
    bool? isLoading,
    List<AlertWithVerifications>? myAlerts,
    List<AlertWithVerifications>? pendingVerificationAlerts,
    AlertWithVerifications? selectedAlert,
    String? error,
    String? errorCode,
    bool clearSelectedAlert = false,
    bool clearError = false,
  }) {
    return AlertState(
      isLoading: isLoading ?? this.isLoading,
      myAlerts: myAlerts ?? this.myAlerts,
      pendingVerificationAlerts:
          pendingVerificationAlerts ?? this.pendingVerificationAlerts,
      selectedAlert:
          clearSelectedAlert ? null : (selectedAlert ?? this.selectedAlert),
      error: clearError ? null : (error ?? this.error),
      errorCode: clearError ? null : (errorCode ?? this.errorCode),
    );
  }

  /// Get active alerts (not resolved)
  List<AlertWithVerifications> get activeAlerts =>
      myAlerts.where((a) => a.alert.status != AlertStatus.resolved).toList();

  /// Get resolved alerts
  List<AlertWithVerifications> get resolvedAlerts =>
      myAlerts.where((a) => a.alert.status == AlertStatus.resolved).toList();

  /// Check if user has any active alert
  bool get hasActiveAlert => activeAlerts.isNotEmpty;

  /// Get the current active alert (if any)
  AlertWithVerifications? get currentActiveAlert =>
      activeAlerts.isNotEmpty ? activeAlerts.first : null;
}

/// Alert Repository provider
final alertRepositoryProvider = Provider<AlertRepository>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  return AlertRepository(apiService: apiService);
});

/// Alert Controller provider using Riverpod
/// Requirements: 9.2 - Riverpod for state management
final alertControllerProvider =
    StateNotifierProvider<AlertController, AlertState>((ref) {
  final repository = ref.watch(alertRepositoryProvider);
  return AlertController(repository);
});

/// Alert management controller
/// Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
/// Requirements: 9.2 - Riverpod for state management
class AlertController extends StateNotifier<AlertState> {
  final AlertRepository _repository;
  Timer? _refreshTimer;

  AlertController(this._repository) : super(const AlertState()) {
    // Load alerts on initialization
    loadAlerts();
  }

  /// Load all alerts for the current user
  Future<void> loadAlerts({bool includeResolved = false}) async {
    state = state.copyWith(isLoading: true, clearError: true);

    final result = await _repository.getMyAlerts(
      includeResolved: includeResolved,
    );

    if (result.isSuccess) {
      state = state.copyWith(
        isLoading: false,
        myAlerts: result.data ?? [],
      );

      // Also load pending verification alerts
      await loadPendingVerificationAlerts();
    } else {
      state = state.copyWith(
        isLoading: false,
        error: result.error,
        errorCode: result.errorCode,
      );
    }
  }

  /// Load alerts pending verification from the current user
  /// Requirements: 3.1 - Multi-person verification (2-of-3 Inner Circle)
  Future<void> loadPendingVerificationAlerts() async {
    final result = await _repository.getPendingVerificationAlerts();

    if (result.isSuccess) {
      state = state.copyWith(
        pendingVerificationAlerts: result.data ?? [],
      );
    }
  }

  /// Create a new alert
  /// Requirements: 3.1 - Multi-person verification requirement
  Future<bool> createAlert({required AlertType type}) async {
    state = state.copyWith(isLoading: true, clearError: true);

    final result = await _repository.createAlert(type: type);

    if (result.isSuccess && result.data != null) {
      // Add new alert to list
      state = state.copyWith(
        isLoading: false,
        myAlerts: [result.data!, ...state.myAlerts],
        selectedAlert: result.data,
      );
      return true;
    }

    state = state.copyWith(
      isLoading: false,
      error: result.error,
      errorCode: result.errorCode,
    );
    return false;
  }


  /// Get a specific alert
  Future<AlertWithVerifications?> getAlert(String alertId) async {
    state = state.copyWith(isLoading: true, clearError: true);

    final result = await _repository.getAlert(alertId);

    if (result.isSuccess && result.data != null) {
      state = state.copyWith(
        isLoading: false,
        selectedAlert: result.data,
      );
      return result.data;
    }

    state = state.copyWith(
      isLoading: false,
      error: result.error,
      errorCode: result.errorCode,
    );
    return null;
  }

  /// Verify an alert (2-of-3 Inner Circle requirement)
  /// Requirements: 3.1 - Multi-person verification (2-of-3 Inner Circle)
  /// Requirements: 3.2 - Notify Inner Circle immediately via encrypted channels
  Future<bool> verifyAlert(String alertId) async {
    state = state.copyWith(isLoading: true, clearError: true);

    final result = await _repository.verifyAlert(alertId);

    if (result.isSuccess) {
      // Reload alerts to get updated verification counts
      await loadAlerts();
      return true;
    }

    state = state.copyWith(
      isLoading: false,
      error: result.error,
      errorCode: result.errorCode,
    );
    return false;
  }

  /// Force escalate an alert to the next level
  /// Requirements: 3.3 - Escalate to Community Circle after 30 minutes
  /// Requirements: 3.4 - Escalate to Professional Circle after 2 hours
  Future<bool> escalateAlert(String alertId) async {
    state = state.copyWith(isLoading: true, clearError: true);

    final result = await _repository.escalateAlert(alertId);

    if (result.isSuccess) {
      // Reload alerts to get updated escalation level
      await loadAlerts();
      return true;
    }

    state = state.copyWith(
      isLoading: false,
      error: result.error,
      errorCode: result.errorCode,
    );
    return false;
  }

  /// Resolve an alert and notify all participants
  /// Requirements: 3.5 - Notify all active participants and close the case
  Future<bool> resolveAlert({
    required String alertId,
    String? resolutionNotesEncrypted,
  }) async {
    state = state.copyWith(isLoading: true, clearError: true);

    final result = await _repository.resolveAlert(
      alertId: alertId,
      resolutionNotesEncrypted: resolutionNotesEncrypted,
    );

    if (result.isSuccess && result.data != null) {
      // Update the alert in the list
      final updatedAlerts = state.myAlerts.map((a) {
        if (a.alert.id == alertId) {
          return result.data!;
        }
        return a;
      }).toList();

      state = state.copyWith(
        isLoading: false,
        myAlerts: updatedAlerts,
        selectedAlert: result.data,
      );
      return true;
    }

    state = state.copyWith(
      isLoading: false,
      error: result.error,
      errorCode: result.errorCode,
    );
    return false;
  }

  /// Select an alert for viewing
  void selectAlert(AlertWithVerifications alert) {
    state = state.copyWith(selectedAlert: alert);
  }

  /// Clear selected alert
  void clearSelectedAlert() {
    state = state.copyWith(clearSelectedAlert: true);
  }

  /// Clear any error state
  void clearError() {
    state = state.copyWith(clearError: true);
  }

  /// Start real-time updates polling
  /// This provides real-time alert status updates
  void startRealTimeUpdates() {
    _stopRealTimeUpdates();

    // Poll every 10 seconds for alert updates (more frequent than circles)
    _refreshTimer = Timer.periodic(
      const Duration(seconds: 10),
      (_) => loadAlerts(),
    );
  }

  /// Stop real-time updates
  void _stopRealTimeUpdates() {
    _refreshTimer?.cancel();
    _refreshTimer = null;
  }

  @override
  void dispose() {
    _stopRealTimeUpdates();
    super.dispose();
  }
}
