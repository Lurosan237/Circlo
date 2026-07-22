import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'core/services/security_service.dart';
import 'core/services/secure_storage_service.dart';
import 'core/services/error_service.dart';
import 'core/services/app_integration_service.dart';
import 'core/theme/app_theme.dart';
import 'core/router/app_router.dart';

void main() async {
  // Capture Flutter framework errors
  FlutterError.onError = (FlutterErrorDetails details) {
    FlutterError.presentError(details);
    if (kReleaseMode) {
      // Log to crash reporting in production
      _logFlutterError(details);
    }
  };

  // Capture async errors not caught by Flutter
  await runZonedGuarded(() async {
    WidgetsFlutterBinding.ensureInitialized();
    
    // Initialize Hive for local encrypted storage
    await Hive.initFlutter();
    
    // Initialize security service
    await SecurityService.initialize();
    
    // Initialize secure storage service
    await SecureStorageService.initialize();
    
    runApp(
      const ProviderScope(
        child: CircloApp(),
      ),
    );
  }, (error, stackTrace) {
    // Handle uncaught async errors
    if (kDebugMode) {
      debugPrint('Uncaught error: $error');
      debugPrint('Stack trace: $stackTrace');
    }
    // In production, send to crash reporting
    _logUncaughtError(error, stackTrace);
  });
}

void _logFlutterError(FlutterErrorDetails details) {
  // Placeholder for crash reporting integration
  // Example: FirebaseCrashlytics.instance.recordFlutterFatalError(details);
  debugPrint('Flutter error logged: ${details.exception}');
}

void _logUncaughtError(Object error, StackTrace stackTrace) {
  // Placeholder for crash reporting integration
  // Example: FirebaseCrashlytics.instance.recordError(error, stackTrace, fatal: true);
  debugPrint('Uncaught error logged: $error');
}

class CircloApp extends ConsumerStatefulWidget {
  const CircloApp({super.key});

  @override
  ConsumerState<CircloApp> createState() => _CircloAppState();
}

class _CircloAppState extends ConsumerState<CircloApp> {
  @override
  void initState() {
    super.initState();
    // Initialize app integration service
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(appIntegrationServiceProvider.notifier).initialize();
    });
  }

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(appRouterProvider);
    final isOffline = ref.watch(isOfflineProvider);
    final appState = ref.watch(appIntegrationServiceProvider);
    
    // Show loading screen while initializing
    if (appState.initState == AppInitState.initializing) {
      return MaterialApp(
        title: 'Circlo Safety',
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        themeMode: ThemeMode.system,
        debugShowCheckedModeBanner: false,
        home: const _LoadingScreen(),
      );
    }
    
    return MaterialApp.router(
      title: 'Circlo Safety',
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeMode.system,
      routerConfig: router,
      debugShowCheckedModeBanner: false,
      builder: (context, child) {
        return _ErrorBoundary(
          child: Column(
            children: [
              // Offline banner
              if (isOffline)
                const _OfflineBanner(),
              // Realtime connection status
              if (appState.isAuthenticated && !appState.isRealtimeConnected)
                const _RealtimeDisconnectedBanner(),
              // Main content
              Expanded(child: child ?? const SizedBox.shrink()),
            ],
          ),
        );
      },
    );
  }
}

/// Loading screen shown during app initialization
class _LoadingScreen extends StatelessWidget {
  const _LoadingScreen();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Initializing Circlo...'),
          ],
        ),
      ),
    );
  }
}

/// Banner shown when realtime connection is lost
class _RealtimeDisconnectedBanner extends StatelessWidget {
  const _RealtimeDisconnectedBanner();

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.amber.shade800,
      child: SafeArea(
        bottom: false,
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 16),
          child: const Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.sync_problem, color: Colors.white, size: 14),
              SizedBox(width: 8),
              Text(
                'Reconnecting to real-time updates...',
                style: TextStyle(color: Colors.white, fontSize: 11),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Error boundary widget for catching widget tree errors
class _ErrorBoundary extends StatefulWidget {
  final Widget child;

  const _ErrorBoundary({required this.child});

  @override
  State<_ErrorBoundary> createState() => _ErrorBoundaryState();
}

class _ErrorBoundaryState extends State<_ErrorBoundary> {
  bool _hasError = false;
  FlutterErrorDetails? _errorDetails;

  @override
  void initState() {
    super.initState();
  }

  void _resetError() {
    setState(() {
      _hasError = false;
      _errorDetails = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_hasError) {
      return _ErrorFallbackWidget(
        errorDetails: _errorDetails,
        onRetry: _resetError,
      );
    }

    return ErrorWidget.builder = (FlutterErrorDetails details) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          setState(() {
            _hasError = true;
            _errorDetails = details;
          });
        }
      });
      return const SizedBox.shrink();
    };
  }
}

/// Fallback widget shown when an error occurs
class _ErrorFallbackWidget extends StatelessWidget {
  final FlutterErrorDetails? errorDetails;
  final VoidCallback onRetry;

  const _ErrorFallbackWidget({
    this.errorDetails,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(
                Icons.error_outline,
                size: 64,
                color: Colors.red,
              ),
              const SizedBox(height: 16),
              const Text(
                'Something went wrong',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'We encountered an unexpected error. Please try again.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey),
              ),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: const Text('Try Again'),
              ),
              if (kDebugMode && errorDetails != null) ...[
                const SizedBox(height: 24),
                Expanded(
                  child: SingleChildScrollView(
                    child: Text(
                      errorDetails!.toString(),
                      style: const TextStyle(
                        fontSize: 12,
                        fontFamily: 'monospace',
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Offline banner shown when device is offline
class _OfflineBanner extends StatelessWidget {
  const _OfflineBanner();

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.orange.shade800,
      child: SafeArea(
        bottom: false,
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
          child: const Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.wifi_off, color: Colors.white, size: 16),
              SizedBox(width: 8),
              Text(
                'You\'re offline. Some features may be unavailable.',
                style: TextStyle(color: Colors.white, fontSize: 12),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
