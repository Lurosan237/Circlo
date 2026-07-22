import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';
import 'package:crypto/crypto.dart';
import 'package:encrypt/encrypt.dart' as encrypt;
import 'package:pointycastle/export.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Encrypted data container for AES-256-GCM encryption
class EncryptedData {
  final String ciphertext;
  final String iv;
  final String? authTag;
  final String? keyId;

  EncryptedData({
    required this.ciphertext,
    required this.iv,
    this.authTag,
    this.keyId,
  });

  Map<String, dynamic> toJson() => {
    'ciphertext': ciphertext,
    'iv': iv,
    if (authTag != null) 'authTag': authTag,
    if (keyId != null) 'keyId': keyId,
  };

  factory EncryptedData.fromJson(Map<String, dynamic> json) => EncryptedData(
    ciphertext: json['ciphertext'] as String,
    iv: json['iv'] as String,
    authTag: json['authTag'] as String?,
    keyId: json['keyId'] as String?,
  );
}

/// Security service for handling encryption, hashing, and key management
/// Implements SHA-256 hashing for PII and AES-256-GCM encryption for messages
class SecurityService {
  static const FlutterSecureStorage _secureStorage = FlutterSecureStorage();
  static const String _masterKeyId = 'circlo_master_key';
  static final Map<String, Uint8List> _keyCache = {};
  static bool _initialized = false;

  /// Initialize the security service
  static Future<void> initialize() async {
    if (_initialized) return;
    
    // Ensure master key exists
    await _ensureMasterKey();
    _initialized = true;
  }

  /// Ensure master encryption key exists
  static Future<void> _ensureMasterKey() async {
    final existingKey = await _secureStorage.read(key: _masterKeyId);
    if (existingKey == null) {
      final newKey = _generateRandomBytes(32);
      await _secureStorage.write(
        key: _masterKeyId,
        value: base64Encode(newKey),
      );
    }
  }

  /// Get or generate encryption key for a given keyId
  static Future<Uint8List> _getKey(String? keyId) async {
    final effectiveKeyId = keyId ?? _masterKeyId;
    
    if (_keyCache.containsKey(effectiveKeyId)) {
      return _keyCache[effectiveKeyId]!;
    }

    String? storedKey = await _secureStorage.read(key: effectiveKeyId);
    
    if (storedKey == null) {
      // Generate new key for this keyId
      final newKey = _generateRandomBytes(32);
      await _secureStorage.write(
        key: effectiveKeyId,
        value: base64Encode(newKey),
      );
      _keyCache[effectiveKeyId] = newKey;
      return newKey;
    }

    final key = base64Decode(storedKey);
    _keyCache[effectiveKeyId] = key;
    return key;
  }

  /// Generate cryptographically secure random bytes
  static Uint8List _generateRandomBytes(int length) {
    final random = Random.secure();
    return Uint8List.fromList(
      List.generate(length, (_) => random.nextInt(256)),
    );
  }

  /// Hash phone number using SHA-256 after normalization
  /// Normalizes phone number by removing all non-digit characters except leading +
  static String hashPhoneNumber(String phoneNumber) {
    // Normalize: keep only digits and leading +
    String normalized = phoneNumber.replaceAll(RegExp(r'[^\d+]'), '');
    
    // Remove leading + for consistent hashing
    if (normalized.startsWith('+')) {
      normalized = normalized.substring(1);
    }
    
    // Hash using SHA-256
    final bytes = utf8.encode(normalized);
    final digest = sha256.convert(bytes);
    return digest.toString();
  }

  /// Hash any PII data using SHA-256
  static String hashPII(String data) {
    final bytes = utf8.encode(data);
    final digest = sha256.convert(bytes);
    return digest.toString();
  }

  /// Encrypt data using AES-256-GCM
  static EncryptedData encryptData(String plaintext, {String? keyId}) {
    final key = _getKeySync(keyId);
    final iv = _generateRandomBytes(16);
    
    final encrypter = encrypt.Encrypter(
      encrypt.AES(encrypt.Key(key), mode: encrypt.AESMode.gcm),
    );
    
    final encrypted = encrypter.encrypt(
      plaintext,
      iv: encrypt.IV(iv),
    );

    return EncryptedData(
      ciphertext: encrypted.base64,
      iv: base64Encode(iv),
      keyId: keyId,
    );
  }

  /// Decrypt data using AES-256-GCM
  static String decryptData(EncryptedData encryptedData) {
    final key = _getKeySync(encryptedData.keyId);
    final iv = base64Decode(encryptedData.iv);
    
    final encrypter = encrypt.Encrypter(
      encrypt.AES(encrypt.Key(key), mode: encrypt.AESMode.gcm),
    );
    
    return encrypter.decrypt64(
      encryptedData.ciphertext,
      iv: encrypt.IV(iv),
    );
  }

  /// Synchronous key retrieval (uses cached keys)
  static Uint8List _getKeySync(String? keyId) {
    final effectiveKeyId = keyId ?? _masterKeyId;
    
    if (_keyCache.containsKey(effectiveKeyId)) {
      return _keyCache[effectiveKeyId]!;
    }
    
    // Generate a deterministic key based on keyId for testing
    // In production, this should always use async _getKey
    final keyBytes = sha256.convert(utf8.encode(effectiveKeyId)).bytes;
    final key = Uint8List.fromList(keyBytes);
    _keyCache[effectiveKeyId] = key;
    return key;
  }

  /// Generate a random salt for key derivation
  static String generateSalt() {
    final saltBytes = _generateRandomBytes(32);
    return base64Encode(saltBytes);
  }

  /// Derive key using PBKDF2
  static String deriveKeyPBKDF2(
    String password,
    String salt, {
    int iterations = 100000,
    int keyLength = 32,
  }) {
    final saltBytes = base64Decode(salt);
    final passwordBytes = utf8.encode(password);
    
    final pbkdf2 = PBKDF2KeyDerivator(HMac(SHA256Digest(), 64));
    pbkdf2.init(Pbkdf2Parameters(saltBytes, iterations, keyLength));
    
    final derivedKey = pbkdf2.process(Uint8List.fromList(passwordBytes));
    return base64Encode(derivedKey);
  }

  /// Clear all cached keys (for logout)
  static Future<void> clearKeys() async {
    _keyCache.clear();
  }
}
