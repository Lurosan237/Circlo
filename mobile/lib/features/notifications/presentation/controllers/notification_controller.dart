import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../core/models/notification.dart';
import '../../../../core/services/notification_service.dart';
import '../../data/notification_repository.dart';

/// State for notification management
class NotificationState {
  final bool isLoading;
  final String? error;
  final NotificationPreferences? preferences;
  final List<NotificationItem> notifications;
  final int totalNotifications;
  final bool hasMore;
  final String? deviceToken;
  final bool isRegistered;

  const NotificationState({
    this.isLoading = false,
    this.error,
    this.preferences,
    this.notifications = const [],
    this.totalNotifications = 0,
    this.hasMore = false,
    this.deviceToken,
    this.isRegistered = false,
  });

  NotificationState copyWith({
    bool? isLoading,
    String? error,
    NotificationPreferences? preferences,
    List<NotificationItem>? notifications,
    int? totalNotifications,
    bool? hasMore,
    String? deviceToken,
    bool? isRegistered,
  }) {
    return NotificationState(
      isLoading: isLoading ?? this.isLoading,
      error: error,
      preferences: preferences ?? this.preferences,
      notifications: notifications ?? this.notifications,
      totalNotifications: totalNotifications ?? this.totalNotifications,
      hasMore: hasMore ?? this.hasMore,
      deviceToken: deviceToken ?? this.deviceToken,
      isRegistered: isRegistered ?? this.isRegistered,
    );
  }
}

/// Controller for notification management
/// 
/// Requirements: 8.1, 8.2, 8.5
/// - FCM client integration
/// - Notification decryption and display
/// - User notification preferences by circle type
class NotificationController extends StateNotifier<NotificationState> {
  final NotificationRepository _repository;
  final NotificationService _notificationService;
  StreamSubscription<NotificationContent>? _notificationSubscription;
  int _currentPage = 1;
  static const int _pageSize = 20;

  NotificationController({
    required NotificationRepository repository,
    required NotificationService notificationService,
  })  : _repository = repository,
        _notificationService = notificationService,
        super(const NotificationState()) {
    _initialize();
  }

  Future<void> _initialize() async {
    await _notificationService.initialize();
    
    // Listen for incoming notifications
    _notificationSubscription = _notificationService.notifications.listen(
      _handleIncomingNotification,
    );
    
    // Load initial data
    await loadPreferences();
  }


  void _handleIncomingNotification(NotificationContent content) {
    // Add to the beginning of the list
    final updatedNotifications = [
      NotificationItem(
        id: content.notificationId,
        userId: '',
        type: content.type.name,
        priority: 'normal',
        status: 'delivered',
        alertId: content.alertId,
        circleId: content.circleId,
        createdAt: content.createdAt,
        title: content.title,
        body: content.body,
        data: content.data,
      ),
      ...state.notifications,
    ];
    
    state = state.copyWith(
      notifications: updatedNotifications,
      totalNotifications: state.totalNotifications + 1,
    );
  }

  /// Register device token with the backend
  /// 
  /// Requirements: 8.1 - Push notifications via Firebase Cloud Messaging
  Future<void> registerDeviceToken(String token, String platform) async {
    state = state.copyWith(isLoading: true, error: null);
    
    final result = await _repository.registerDeviceToken(
      token: token,
      platform: platform,
    );
    
    if (result.isSuccess) {
      await _notificationService.saveDeviceToken(token);
      state = state.copyWith(
        isLoading: false,
        deviceToken: token,
        isRegistered: true,
      );
    } else {
      state = state.copyWith(
        isLoading: false,
        error: result.error,
      );
    }
  }

  /// Unregister device token
  Future<void> unregisterDeviceToken() async {
    final token = state.deviceToken ?? _notificationService.currentToken;
    if (token == null) return;
    
    state = state.copyWith(isLoading: true, error: null);
    
    final result = await _repository.unregisterDeviceToken(token);
    
    if (result.isSuccess) {
      await _notificationService.clearDeviceToken();
      state = state.copyWith(
        isLoading: false,
        deviceToken: null,
        isRegistered: false,
      );
    } else {
      state = state.copyWith(
        isLoading: false,
        error: result.error,
      );
    }
  }

  /// Load notification preferences
  /// 
  /// Requirements: 8.5 - User notification preferences by circle type
  Future<void> loadPreferences() async {
    state = state.copyWith(isLoading: true, error: null);
    
    final result = await _repository.getPreferences();
    
    if (result.isSuccess && result.data != null) {
      await _notificationService.updatePreferences(result.data!);
      state = state.copyWith(
        isLoading: false,
        preferences: result.data,
      );
    } else {
      state = state.copyWith(
        isLoading: false,
        error: result.error,
      );
    }
  }

  /// Update notification preferences
  /// 
  /// Requirements: 8.5 - User notification preferences by circle type
  Future<void> updatePreferences({
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
    state = state.copyWith(isLoading: true, error: null);
    
    final result = await _repository.updatePreferences(
      innerCircleEnabled: innerCircleEnabled,
      communityCircleEnabled: communityCircleEnabled,
      professionalCircleEnabled: professionalCircleEnabled,
      alertNotifications: alertNotifications,
      messageNotifications: messageNotifications,
      circleNotifications: circleNotifications,
      systemNotifications: systemNotifications,
      quietHoursEnabled: quietHoursEnabled,
      quietHoursStart: quietHoursStart,
      quietHoursEnd: quietHoursEnd,
    );
    
    if (result.isSuccess && result.data != null) {
      await _notificationService.updatePreferences(result.data!);
      state = state.copyWith(
        isLoading: false,
        preferences: result.data,
      );
    } else {
      state = state.copyWith(
        isLoading: false,
        error: result.error,
      );
    }
  }


  /// Load notifications with pagination
  Future<void> loadNotifications({bool refresh = false}) async {
    if (refresh) {
      _currentPage = 1;
    }
    
    state = state.copyWith(isLoading: true, error: null);
    
    final result = await _repository.getNotifications(
      page: _currentPage,
      pageSize: _pageSize,
      includeContent: true,
    );
    
    if (result.isSuccess && result.data != null) {
      final data = result.data!;
      
      List<NotificationItem> updatedNotifications;
      if (refresh || _currentPage == 1) {
        updatedNotifications = data.notifications;
      } else {
        updatedNotifications = [...state.notifications, ...data.notifications];
      }
      
      state = state.copyWith(
        isLoading: false,
        notifications: updatedNotifications,
        totalNotifications: data.total,
        hasMore: data.hasMore,
      );
    } else {
      state = state.copyWith(
        isLoading: false,
        error: result.error,
      );
    }
  }

  /// Load more notifications (pagination)
  Future<void> loadMoreNotifications() async {
    if (!state.hasMore || state.isLoading) return;
    
    _currentPage++;
    await loadNotifications();
  }

  /// Mark notification as delivered
  Future<void> markAsDelivered(String notificationId) async {
    await _repository.markAsDelivered(notificationId);
  }

  /// Handle incoming FCM notification
  Future<void> handleFCMNotification(Map<String, dynamic> message) async {
    await _notificationService.handleNotification(message);
  }

  /// Clear error state
  void clearError() {
    state = state.copyWith(error: null);
  }

  @override
  void dispose() {
    _notificationSubscription?.cancel();
    _notificationService.dispose();
    super.dispose();
  }
}
