import 'package:flutter/material.dart';

/// App theme configuration using Material 3 design system
class AppTheme {
  AppTheme._();

  // Brand colors
  static const Color _primaryColor = Color(0xFF2563EB);
  static const Color _secondaryColor = Color(0xFF7C3AED);
  static const Color _errorColor = Color(0xFFDC2626);
  static const Color _warningColor = Color(0xFFF59E0B);
  static const Color _successColor = Color(0xFF10B981);

  /// Light theme configuration
  static ThemeData get lightTheme {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: _primaryColor,
      brightness: Brightness.light,
      error: _errorColor,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      appBarTheme: AppBarTheme(
        centerTitle: true,
        elevation: 0,
        backgroundColor: colorScheme.surface,
        foregroundColor: colorScheme.onSurface,
      ),
      cardTheme: CardTheme(
        elevation: 2,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
    );
  }

  /// Dark theme configuration
  static ThemeData get darkTheme {
    final colorScheme = ColorScheme.fromSeed(
      seedColor: _primaryColor,
      brightness: Brightness.dark,
      error: _errorColor,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      appBarTheme: AppBarTheme(
        centerTitle: true,
        elevation: 0,
        backgroundColor: colorScheme.surface,
        foregroundColor: colorScheme.onSurface,
      ),
      cardTheme: CardTheme(
        elevation: 2,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      ),
      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
    );
  }

  // Custom colors for circle types
  static const Color innerCircleColor = Color(0xFFDC2626);
  static const Color communityCircleColor = Color(0xFFF59E0B);
  static const Color professionalCircleColor = Color(0xFF2563EB);

  // Alert status colors
  static const Color alertPendingColor = Color(0xFFF59E0B);
  static const Color alertVerifiedColor = Color(0xFF10B981);
  static const Color alertEscalatedColor = Color(0xFFDC2626);
  static const Color alertResolvedColor = Color(0xFF6B7280);
}
