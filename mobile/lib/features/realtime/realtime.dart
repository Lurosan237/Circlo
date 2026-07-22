/// Real-time communication feature module
/// 
/// Requirements: 5.1, 5.2, 5.3, 5.4
/// - Implement Socket.io client with encryption support
/// - Create encrypted message handling for active alerts
/// - Add real-time UI updates for alert status changes
/// - Implement local message decryption

// Data layer
export 'data/message_repository.dart';

// Presentation layer
export 'presentation/controllers/realtime_controller.dart';
export 'presentation/widgets/chat_widget.dart';
