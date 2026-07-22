import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/models/circle.dart';
import '../../../../core/services/api_service.dart';
import '../../../auth/presentation/controllers/auth_controller.dart';
import '../../data/circle_repository.dart';

/// Circle management state
class CircleState {
  final bool isLoading;
  final List<Circle> circles;
  final List<PendingInvitation> pendingInvitations;
  final Circle? selectedCircle;
  final String? error;
  final String? errorCode;

  const CircleState({
    this.isLoading = false,
    this.circles = const [],
    this.pendingInvitations = const [],
    this.selectedCircle,
    this.error,
    this.errorCode,
  });

  CircleState copyWith({
    bool? isLoading,
    List<Circle>? circles,
    List<PendingInvitation>? pendingInvitations,
    Circle? selectedCircle,
    String? error,
    String? errorCode,
    bool clearSelectedCircle = false,
    bool clearError = false,
  }) {
    return CircleState(
      isLoading: isLoading ?? this.isLoading,
      circles: circles ?? this.circles,
      pendingInvitations: pendingInvitations ?? this.pendingInvitations,
      selectedCircle: clearSelectedCircle ? null : (selectedCircle ?? this.selectedCircle),
      error: clearError ? null : (error ?? this.error),
      errorCode: clearError ? null : (errorCode ?? this.errorCode),
    );
  }

  /// Get circles by type
  List<Circle> getCirclesByType(CircleType type) {
    return circles.where((c) => c.type == type).toList();
  }

  /// Get inner circles
  List<Circle> get innerCircles => getCirclesByType(CircleType.inner);

  /// Get community circles
  List<Circle> get communityCircles => getCirclesByType(CircleType.community);

  /// Get professional circles
  List<Circle> get professionalCircles => getCirclesByType(CircleType.professional);
}

/// Circle Repository provider
final circleRepositoryProvider = Provider<CircleRepository>((ref) {
  final apiService = ref.watch(apiServiceProvider);
  return CircleRepository(apiService: apiService);
});

/// Circle Controller provider using Riverpod
/// Requirements: 9.2 - Riverpod for state management
final circleControllerProvider =
    StateNotifierProvider<CircleController, CircleState>((ref) {
  final repository = ref.watch(circleRepositoryProvider);
  return CircleController(repository);
});

/// Circle management controller
/// Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
/// Requirements: 9.2 - Riverpod for state management
class CircleController extends StateNotifier<CircleState> {
  final CircleRepository _repository;
  Timer? _refreshTimer;

  CircleController(this._repository) : super(const CircleState()) {
    // Load circles on initialization
    loadCircles();
  }

  /// Load all circles for the current user
  Future<void> loadCircles() async {
    state = state.copyWith(isLoading: true, clearError: true);

    final result = await _repository.getCircles();

    if (result.isSuccess) {
      state = state.copyWith(
        isLoading: false,
        circles: result.data ?? [],
      );
      
      // Also load pending invitations
      await loadPendingInvitations();
    } else {
      state = state.copyWith(
        isLoading: false,
        error: result.error,
        errorCode: result.errorCode,
      );
    }
  }

  /// Load pending invitations
  /// Requirements: 2.4 - Mutual verification requirement
  Future<void> loadPendingInvitations() async {
    final result = await _repository.getPendingInvitations();

    if (result.isSuccess) {
      state = state.copyWith(
        pendingInvitations: result.data ?? [],
      );
    }
  }

  /// Create a new circle
  /// Requirements: 2.1 - Inner Circle: 3-5 members
  /// Requirements: 2.2 - Community Circle: 15-30 members
  /// Requirements: 2.3 - Professional Circle: verified resources
  Future<bool> createCircle({
    required CircleType type,
    required String nameEncrypted,
    required int maxMembers,
  }) async {
    state = state.copyWith(isLoading: true, clearError: true);

    final result = await _repository.createCircle(
      type: type,
      nameEncrypted: nameEncrypted,
      maxMembers: maxMembers,
    );

    if (result.isSuccess && result.data != null) {
      // Add new circle to list
      state = state.copyWith(
        isLoading: false,
        circles: [...state.circles, result.data!],
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

  /// Get a specific circle
  /// Requirements: 2.5 - Role-based permissions
  Future<Circle?> getCircle(String circleId) async {
    state = state.copyWith(isLoading: true, clearError: true);

    final result = await _repository.getCircle(circleId);

    if (result.isSuccess && result.data != null) {
      state = state.copyWith(
        isLoading: false,
        selectedCircle: result.data,
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

  /// Delete a circle
  /// Requirements: 2.5 - Role-based permissions
  Future<bool> deleteCircle(String circleId) async {
    state = state.copyWith(isLoading: true, clearError: true);

    final result = await _repository.deleteCircle(circleId);

    if (result.isSuccess) {
      // Remove circle from list
      state = state.copyWith(
        isLoading: false,
        circles: state.circles.where((c) => c.id != circleId).toList(),
        clearSelectedCircle: state.selectedCircle?.id == circleId,
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

  /// Add a member to a circle
  /// Requirements: 2.4 - Mutual verification before activation
  Future<bool> addMember({
    required String circleId,
    required String userId,
  }) async {
    state = state.copyWith(isLoading: true, clearError: true);

    final result = await _repository.addMember(
      circleId: circleId,
      userId: userId,
    );

    if (result.isSuccess) {
      // Refresh the circle to get updated members
      await getCircle(circleId);
      state = state.copyWith(isLoading: false);
      return true;
    }

    state = state.copyWith(
      isLoading: false,
      error: result.error,
      errorCode: result.errorCode,
    );
    return false;
  }

  /// Verify membership (accept invitation)
  /// Requirements: 2.4 - Mutual verification before activation
  Future<bool> verifyMembership(String circleId) async {
    state = state.copyWith(isLoading: true, clearError: true);

    final result = await _repository.verifyMembership(circleId);

    if (result.isSuccess) {
      // Reload circles and invitations
      await loadCircles();
      return true;
    }

    state = state.copyWith(
      isLoading: false,
      error: result.error,
      errorCode: result.errorCode,
    );
    return false;
  }

  /// Remove a member from a circle
  /// Requirements: 2.6 - Immediate access revocation on removal
  Future<bool> removeMember({
    required String circleId,
    required String userId,
  }) async {
    state = state.copyWith(isLoading: true, clearError: true);

    final result = await _repository.removeMember(
      circleId: circleId,
      userId: userId,
    );

    if (result.isSuccess) {
      // Refresh the circle to get updated members
      await getCircle(circleId);
      state = state.copyWith(isLoading: false);
      return true;
    }

    state = state.copyWith(
      isLoading: false,
      error: result.error,
      errorCode: result.errorCode,
    );
    return false;
  }

  /// Leave a circle
  /// Requirements: 2.6 - Immediate access revocation
  Future<bool> leaveCircle(String circleId) async {
    state = state.copyWith(isLoading: true, clearError: true);

    final result = await _repository.leaveCircle(circleId);

    if (result.isSuccess) {
      // Remove circle from list
      state = state.copyWith(
        isLoading: false,
        circles: state.circles.where((c) => c.id != circleId).toList(),
        clearSelectedCircle: state.selectedCircle?.id == circleId,
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

  /// Select a circle for viewing
  void selectCircle(Circle circle) {
    state = state.copyWith(selectedCircle: circle);
  }

  /// Clear selected circle
  void clearSelectedCircle() {
    state = state.copyWith(clearSelectedCircle: true);
  }

  /// Clear any error state
  void clearError() {
    state = state.copyWith(clearError: true);
  }

  /// Start real-time updates polling
  void startRealTimeUpdates() {
    _stopRealTimeUpdates();
    
    // Poll every 30 seconds for updates
    _refreshTimer = Timer.periodic(
      const Duration(seconds: 30),
      (_) => loadCircles(),
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
