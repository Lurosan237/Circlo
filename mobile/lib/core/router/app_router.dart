import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../features/auth/presentation/pages/login_page.dart';
import '../../features/auth/presentation/pages/register_page.dart';
import '../../features/home/presentation/pages/home_page.dart';
import '../../features/circles/presentation/pages/circles_page.dart';
import '../../features/circles/presentation/pages/circle_detail_page.dart';
import '../../features/circles/presentation/pages/create_circle_page.dart';
import '../../features/alerts/presentation/pages/alerts_page.dart';
import '../../features/alerts/presentation/pages/create_alert_page.dart';
import '../../features/alerts/presentation/pages/alert_detail_page.dart';
import '../services/app_integration_service.dart';

/// App router provider using GoRouter
final appRouterProvider = Provider<GoRouter>((ref) {
  final appState = ref.watch(appIntegrationServiceProvider);
  
  return GoRouter(
    initialLocation: '/login',
    redirect: (context, state) {
      final isLoggedIn = appState.isAuthenticated;
      final isLoggingIn = state.matchedLocation == '/login' || 
                          state.matchedLocation == '/register';
      
      // If not logged in and not on login/register page, redirect to login
      if (!isLoggedIn && !isLoggingIn) {
        return '/login';
      }
      
      // If logged in and on login/register page, redirect to home
      if (isLoggedIn && isLoggingIn) {
        return '/home';
      }
      
      return null;
    },
    routes: [
      GoRoute(
        path: '/login',
        name: 'login',
        builder: (context, state) => const LoginPage(),
      ),
      GoRoute(
        path: '/register',
        name: 'register',
        builder: (context, state) => const RegisterPage(),
      ),
      GoRoute(
        path: '/home',
        name: 'home',
        builder: (context, state) => const HomePage(),
      ),
      GoRoute(
        path: '/circles',
        name: 'circles',
        builder: (context, state) => const CirclesPage(),
        routes: [
          GoRoute(
            path: 'create',
            name: 'create-circle',
            builder: (context, state) => const CreateCirclePage(),
          ),
          GoRoute(
            path: 'detail',
            name: 'circle-detail',
            builder: (context, state) {
              final circleId = state.extra as String? ?? '';
              return CircleDetailPage(circleId: circleId);
            },
          ),
        ],
      ),
      GoRoute(
        path: '/alerts',
        name: 'alerts',
        builder: (context, state) => const AlertsPage(),
        routes: [
          GoRoute(
            path: 'create',
            name: 'create-alert',
            builder: (context, state) => const CreateAlertPage(),
          ),
          GoRoute(
            path: 'detail/:alertId',
            name: 'alert-detail',
            builder: (context, state) {
              final alertId = state.pathParameters['alertId'] ?? '';
              return AlertDetailPage(alertId: alertId);
            },
          ),
        ],
      ),
    ],
    errorBuilder: (context, state) => Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 64, color: Colors.red),
            const SizedBox(height: 16),
            Text('Page not found: ${state.uri}'),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () => context.go('/home'),
              child: const Text('Go Home'),
            ),
          ],
        ),
      ),
    ),
  );
});
