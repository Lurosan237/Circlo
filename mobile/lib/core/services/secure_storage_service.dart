import 'dart:convert';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'security_service.dart';

/// Secure storage service using Hive with encryption
/// Requirements: 7.3 - Store data locally using Hive encrypted storage
class SecureStorageService {
  static const String _boxName = 'circlo_secure_box';
  static const String _encryptionKeyName = 'hive_encryption_key';
  static const FlutterSecureStorage _secureStorage = FlutterSecureStorage();
  
  static Box<String>? _box;
  static bool _initialized = false;

  /// Initialize the secure storage service
  static Future<void> initialize() async {
    if (_initialized) return;
    
    // Get or create encryption key
    final encryptionKey = await _getOrCreateEncryptionKey();
    
    // Open encrypted Hive box
    _box = await Hive.openBox<String>(
      _boxName,
      encryptionCipher: HiveAesCipher(encryptionKey),
    );
    
    _initialized = true;
  }

  /// Get or create Hive encryption key
  static Future<List<int>> _getOrCreateEncryptionKey() async {
    String? existingKey = await _secureStorage.read(key: _encryptionKeyName);
    
    if (existingKey != null) {
      return base64Decode(existingKey);
    }
    
    // Generate new encryption key
    final newKey = Hive.generateSecureKey();
    await _secureStorage.write(
      key: _encryptionKeyName,
      value: base64Encode(newKey),
    );
    
    return newKey;
  }

  /// Store a value securely
  static Future<void> write(String key, String value) async {
    await _ensureInitialized();
    
    // Encrypt value before storing
    final encrypted = SecurityService.encryptData(value);
    final encryptedJson = jsonEncode(encrypted.toJson());
    
    await _box!.put(key, encryptedJson);
  }

  /// Read a value from secure storage
  static Future<String?> read(String key) async {
    await _ensureInitialized();
    
    final encryptedJson = _box!.get(key);
    if (encryptedJson == null) return null;
    
    try {
      final encryptedData = EncryptedData.fromJson(
        jsonDecode(encryptedJson) as Map<String, dynamic>,
      );
      return SecurityService.decryptData(encryptedData);
    } catch (e) {
      // If decryption fails, remove corrupted data
      await delete(key);
      return null;
    }
  }

  /// Delete a value from secure storage
  static Future<void> delete(String key) async {
    await _ensureInitialized();
    await _box!.delete(key);
  }

  /// Check if a key exists
  static Future<bool> containsKey(String key) async {
    await _ensureInitialized();
    return _box!.containsKey(key);
  }

  /// Clear all stored data
  static Future<void> clear() async {
    await _ensureInitialized();
    await _box!.clear();
  }

  /// Ensure service is initialized
  static Future<void> _ensureInitialized() async {
    if (!_initialized) {
      await initialize();
    }
  }

  /// Close the storage (for cleanup)
  static Future<void> close() async {
    if (_box != null && _box!.isOpen) {
      await _box!.close();
    }
    _initialized = false;
  }
}

/// Token storage keys
class TokenStorageKeys {
  static const String accessToken = 'access_token';
  static const String refreshToken = 'refresh_token';
  static const String tokenExpiry = 'token_expiry';
  static const String userId = 'user_id';
}

/// Token storage service for authentication tokens
/// Requirements: 1.2 - JWT token with 24-hour expiry
class TokenStorageService {
  /// Store authentication tokens
  static Future<void> storeTokens({
    required String accessToken,
    String? refreshToken,
    DateTime? expiry,
    String? userId,
  }) async {
    await SecureStorageService.write(
      TokenStorageKeys.accessToken,
      accessToken,
    );
    
    if (refreshToken != null) {
      await SecureStorageService.write(
        TokenStorageKeys.refreshToken,
        refreshToken,
      );
    }
    
    if (expiry != null) {
      await SecureStorageService.write(
        TokenStorageKeys.tokenExpiry,
        expiry.toIso8601String(),
      );
    }
    
    if (userId != null) {
      await SecureStorageService.write(
        TokenStorageKeys.userId,
        userId,
      );
    }
  }

  /// Get access token
  static Future<String?> getAccessToken() async {
    return await SecureStorageService.read(TokenStorageKeys.accessToken);
  }

  /// Get refresh token
  static Future<String?> getRefreshToken() async {
    return await SecureStorageService.read(TokenStorageKeys.refreshToken);
  }

  /// Get token expiry
  static Future<DateTime?> getTokenExpiry() async {
    final expiryStr = await SecureStorageService.read(
      TokenStorageKeys.tokenExpiry,
    );
    if (expiryStr == null) return null;
    return DateTime.tryParse(expiryStr);
  }

  /// Get stored user ID
  static Future<String?> getUserId() async {
    return await SecureStorageService.read(TokenStorageKeys.userId);
  }

  /// Check if token is expired
  static Future<bool> isTokenExpired() async {
    final expiry = await getTokenExpiry();
    if (expiry == null) return true;
    return DateTime.now().isAfter(expiry);
  }

  /// Check if user has valid tokens
  static Future<bool> hasValidTokens() async {
    final token = await getAccessToken();
    if (token == null) return false;
    
    final isExpired = await isTokenExpired();
    return !isExpired;
  }

  /// Clear all tokens
  static Future<void> clearTokens() async {
    await SecureStorageService.delete(TokenStorageKeys.accessToken);
    await SecureStorageService.delete(TokenStorageKeys.refreshToken);
    await SecureStorageService.delete(TokenStorageKeys.tokenExpiry);
    await SecureStorageService.delete(TokenStorageKeys.userId);
  }
}
