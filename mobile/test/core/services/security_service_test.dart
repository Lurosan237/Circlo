import 'dart:math';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:circlo_safety/core/services/security_service.dart';

void main() {
  // Initialize Flutter binding for tests
  TestWidgetsFlutterBinding.ensureInitialized();
  
  group('SecurityService Property Tests', () {
    group('Phone Number Hashing Properties', () {
      test('Property 1: Phone Number Hashing - Feature: circlo-safety-app, Property 1: Phone Number Hashing', () {
        // **Validates: Requirements 1.1**
        final random = Random();
        
        // Run property test with 100 iterations
        for (int i = 0; i < 100; i++) {
          // Generate random phone numbers with different formats
          final phoneNumber = _generateRandomPhoneNumber(random);
          
          // Hash the phone number
          final hashedPhone = SecurityService.hashPhoneNumber(phoneNumber);
          
          // Property 1: Hash should be a valid SHA-256 hash (64 hex characters)
          expect(hashedPhone, matches(RegExp(r'^[a-f0-9]{64}$')), 
              reason: 'Hash should be 64 hex characters for phone: $phoneNumber');
          
          // Property 2: Hash should be deterministic (same input = same output)
          final hashedAgain = SecurityService.hashPhoneNumber(phoneNumber);
          expect(hashedPhone, equals(hashedAgain),
              reason: 'Hash should be deterministic for phone: $phoneNumber');
          
          // Property 3: Hash should not contain original phone number
          expect(hashedPhone, isNot(contains(phoneNumber.replaceAll(RegExp(r'[^\d]'), ''))),
              reason: 'Hash should not contain original phone digits');
          
          // Property 4: Different phone numbers should produce different hashes
          final differentPhone = _generateRandomPhoneNumber(random);
          if (phoneNumber != differentPhone) {
            final differentHash = SecurityService.hashPhoneNumber(differentPhone);
            expect(hashedPhone, isNot(equals(differentHash)),
                reason: 'Different phones should produce different hashes');
          }
        }
      });

      test('Property Test: PII Hashing consistency', () {
        final random = Random();
        
        for (int i = 0; i < 50; i++) {
          final piiData = _generateRandomPII(random);
          
          // Hash the PII
          final hashedPII = SecurityService.hashPII(piiData);
          
          // Should be valid SHA-256 hash
          expect(hashedPII, matches(RegExp(r'^[a-f0-9]{64}$')));
          
          // Should be deterministic
          final hashedAgain = SecurityService.hashPII(piiData);
          expect(hashedPII, equals(hashedAgain));
          
          // Should not contain original data
          expect(hashedPII, isNot(contains(piiData)));
        }
      });
    });

    group('Encryption Properties', () {
      test('Property 13: End-to-End Encryption - Feature: circlo-safety-app, Property 13: End-to-End Encryption', () {
        // **Validates: Requirements 5.1, 5.2, 5.3**
        final random = Random();
        
        for (int i = 0; i < 100; i++) {
          // Use longer plaintext to avoid false positives with single characters
          final plaintext = _generateRandomString(random, random.nextInt(100) + 10);
          
          // Property 1: Encrypt then decrypt should return original (round-trip)
          final encrypted = SecurityService.encryptData(plaintext);
          final decrypted = SecurityService.decryptData(encrypted);
          
          expect(decrypted, equals(plaintext),
              reason: 'End-to-end encryption round-trip should preserve original message');
          
          // Property 2: Encrypted data should not contain full plaintext (only check for longer strings)
          if (plaintext.length > 5) {
            expect(encrypted.ciphertext.contains(plaintext), isFalse,
                reason: 'Ciphertext should not contain full original plaintext');
          }
          expect(encrypted.iv, isNotEmpty,
              reason: 'IV should be present for AES-256-GCM');
          
          // Property 3: Each encryption should use different IV (semantic security)
          final encrypted2 = SecurityService.encryptData(plaintext);
          expect(encrypted.iv, isNot(equals(encrypted2.iv)),
              reason: 'Each encryption should use unique IV for semantic security');
        }
      });
    });

    group('Key Derivation Properties', () {
      test('Property Test: PBKDF2 key derivation consistency', () {
        final random = Random();
        
        for (int i = 0; i < 50; i++) {
          final password = _generateRandomString(random, random.nextInt(50) + 8);
          final salt = SecurityService.generateSalt();
          final iterations = 1000 + random.nextInt(9000); // 1000-10000
          
          // Derive key
          final derivedKey1 = SecurityService.deriveKeyPBKDF2(password, salt, iterations: iterations);
          final derivedKey2 = SecurityService.deriveKeyPBKDF2(password, salt, iterations: iterations);
          
          // Should be deterministic
          expect(derivedKey1, equals(derivedKey2),
              reason: 'Key derivation should be deterministic');
          
          // Should not contain password
          expect(derivedKey1, isNot(contains(password)));
          
          // Different passwords should produce different keys
          final differentPassword = _generateRandomString(random, random.nextInt(50) + 8);
          if (password != differentPassword) {
            final differentKey = SecurityService.deriveKeyPBKDF2(differentPassword, salt, iterations: iterations);
            expect(derivedKey1, isNot(equals(differentKey)),
                reason: 'Different passwords should produce different keys');
          }
          
          // Different salts should produce different keys
          final differentSalt = SecurityService.generateSalt();
          final keyWithDifferentSalt = SecurityService.deriveKeyPBKDF2(password, differentSalt, iterations: iterations);
          expect(derivedKey1, isNot(equals(keyWithDifferentSalt)),
              reason: 'Different salts should produce different keys');
        }
      });
    });
  });
}

/// Generate random phone number for testing
String _generateRandomPhoneNumber(Random random) {
  final formats = [
    // US formats
    '+1${_randomDigits(random, 10)}',
    '${_randomDigits(random, 3)}-${_randomDigits(random, 3)}-${_randomDigits(random, 4)}',
    '(${_randomDigits(random, 3)}) ${_randomDigits(random, 3)}-${_randomDigits(random, 4)}',
    '${_randomDigits(random, 10)}',
    // International formats
    '+44${_randomDigits(random, 10)}',
    '+33${_randomDigits(random, 9)}',
    '+49${_randomDigits(random, 11)}',
  ];
  
  return formats[random.nextInt(formats.length)];
}

/// Generate random digits
String _randomDigits(Random random, int count) {
  return List.generate(count, (_) => random.nextInt(10).toString()).join();
}

/// Generate random PII data for testing
String _generateRandomPII(Random random) {
  final types = [
    'john.doe@example.com',
    'Jane Smith',
    '123-45-6789',
    '123 Main St, Anytown, USA',
    'Driver License: D123456789',
  ];
  
  // Sometimes generate completely random strings
  if (random.nextBool()) {
    return _generateRandomString(random, random.nextInt(100) + 5);
  }
  
  return types[random.nextInt(types.length)] + _randomDigits(random, random.nextInt(5));
}

/// Generate random string for testing
String _generateRandomString(Random random, int length) {
  const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  return List.generate(length, (_) => chars[random.nextInt(chars.length)]).join();
}
