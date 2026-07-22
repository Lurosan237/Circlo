/// Authentication feature exports
/// 
/// This module provides authentication functionality including:
/// - User registration with phone hashing (Requirements: 1.1)
/// - Login with JWT token generation (Requirements: 1.2)
/// - Secure token storage using Hive (Requirements: 7.3)
/// - Automatic token refresh mechanism (Requirements: 1.2)
/// - Riverpod state management (Requirements: 9.2)

// Data layer
export 'data/auth_repository.dart';

// Presentation layer
export 'presentation/controllers/auth_controller.dart';
export 'presentation/pages/login_page.dart';
export 'presentation/pages/register_page.dart';
