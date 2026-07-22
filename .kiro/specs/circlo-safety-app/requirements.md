# Requirements Document

## Introduction

Circlo is a safety application designed to help locate missing persons through verified Safety Circles rather than mass location broadcasts. The system uses three concentric trust circles (Inner, Community, Professional) with verified relationships and location-aware check requests to provide targeted assistance when someone goes missing.

## Glossary

- **Safety_Circle**: A verified group of trusted contacts organized in concentric circles of trust
- **Inner_Circle**: 3-5 family members and close friends with highest trust level
- **Community_Circle**: 15-30 trusted neighbors and local contacts
- **Professional_Circle**: Local emergency resources and verified professionals
- **Alert_System**: The mechanism for triggering and distributing missing person alerts
- **Check_Request**: Location-aware request for contacts to verify safety along known routes
- **Encryption_Service**: End-to-end encryption system for all sensitive communications
- **Route_Data**: Locally stored commute and travel patterns (never transmitted)
- **Verification_System**: Multi-person confirmation system for alert authenticity

## Requirements

### Requirement 1: User Authentication System

**User Story:** As a user, I want to securely register and authenticate with the system, so that my identity is verified while maintaining privacy.

#### Acceptance Criteria

1. WHEN a user registers with a phone number, THE Authentication_System SHALL hash the phone number locally using SHA-256 before transmission
2. WHEN a user logs in, THE Authentication_System SHALL validate credentials and issue a JWT token with 24-hour expiry
3. WHEN authentication fails, THE Authentication_System SHALL return consistent error responses without revealing user existence
4. THE Authentication_System SHALL enforce rate limiting to prevent brute force attacks
5. WHEN a JWT token expires, THE Authentication_System SHALL require re-authentication

### Requirement 2: Safety Circle Management

**User Story:** As a user, I want to create and manage three types of safety circles, so that I can organize my trusted contacts by relationship and trust level.

#### Acceptance Criteria

1. WHEN a user creates an Inner Circle, THE Circle_Management_System SHALL limit membership to 3-5 verified contacts
2. WHEN a user creates a Community Circle, THE Circle_Management_System SHALL limit membership to 15-30 verified contacts
3. WHEN a user creates a Professional Circle, THE Circle_Management_System SHALL allow verified local emergency resources
4. WHEN adding contacts to circles, THE Circle_Management_System SHALL require mutual verification before activation
5. THE Circle_Management_System SHALL enforce role-based permissions for each circle type
6. WHEN a contact is removed from a circle, THE Circle_Management_System SHALL immediately revoke their access to user data

### Requirement 3: Smart Alert System

**User Story:** As a user, I want to trigger verified alerts that flow through my safety circles, so that appropriate people are notified when I go missing.

#### Acceptance Criteria

1. WHEN an alert is triggered, THE Alert_System SHALL require verification from 2-of-3 Inner Circle members before activation
2. WHEN an alert is verified, THE Alert_System SHALL notify Inner Circle members immediately via encrypted channels
3. IF Inner Circle cannot locate the person within 30 minutes, THEN THE Alert_System SHALL escalate to Community Circle
4. IF Community Circle cannot locate the person within 2 hours, THEN THE Alert_System SHALL escalate to Professional Circle
5. WHEN an alert is resolved, THE Alert_System SHALL notify all active participants and close the case
6. THE Alert_System SHALL maintain an encrypted audit trail of all alert activities

### Requirement 4: Location-Aware Check Requests

**User Story:** As a circle member, I want to receive location-aware check requests based on the missing person's known routes, so that I can efficiently help search relevant areas.

#### Acceptance Criteria

1. WHEN generating check requests, THE Location_Service SHALL use locally stored route data without transmitting it
2. WHEN a circle member is near a known route, THE Location_Service SHALL send targeted check requests
3. THE Location_Service SHALL create geofences around common locations using Mapbox SDK
4. WHEN check requests are sent, THE Location_Service SHALL include relevant location context without revealing exact routes
5. THE Location_Service SHALL never store or transmit persistent location data

### Requirement 5: Encrypted Communication Channel

**User Story:** As a circle member, I want to communicate securely during an active alert, so that sensitive information remains protected.

#### Acceptance Criteria

1. WHEN an alert is active, THE Communication_System SHALL establish end-to-end encrypted channels using AES-256-GCM
2. WHEN messages are sent, THE Communication_System SHALL encrypt all content before transmission
3. WHEN messages are received, THE Communication_System SHALL decrypt content locally on the device
4. THE Communication_System SHALL provide real-time updates via Socket.io with encrypted payloads
5. WHEN an alert is resolved, THE Communication_System SHALL automatically delete all message history after 90 days

### Requirement 6: Law Enforcement Portal

**User Story:** As a law enforcement officer, I want access to a read-only dashboard for verified missing person cases, so that I can coordinate official search efforts.

#### Acceptance Criteria

1. WHEN law enforcement requests access, THE Portal_System SHALL verify official credentials before granting access
2. WHEN displaying case information, THE Portal_System SHALL show only essential details without revealing personal data
3. THE Portal_System SHALL provide read-only access to active alert status and general location areas
4. WHEN cases are resolved, THE Portal_System SHALL update status and remove sensitive information
5. THE Portal_System SHALL maintain audit logs of all law enforcement access

### Requirement 7: Data Security and Privacy

**User Story:** As a user, I want my personal information to be secure and private, so that my data cannot be misused or accessed by unauthorized parties.

#### Acceptance Criteria

1. WHEN storing user data, THE Security_System SHALL hash all personally identifiable information locally before transmission
2. THE Security_System SHALL implement Row-Level Security policies in PostgreSQL for data isolation
3. WHEN route data is collected, THE Security_System SHALL store it only locally using Hive encrypted storage
4. THE Security_System SHALL automatically delete all user data after 90 days of inactivity
5. THE Security_System SHALL never implement persistent location tracking features

### Requirement 8: Real-Time Notifications

**User Story:** As a circle member, I want to receive immediate notifications about alerts and updates, so that I can respond quickly to help locate missing persons.

#### Acceptance Criteria

1. WHEN alerts are triggered, THE Notification_System SHALL send push notifications via Firebase Cloud Messaging
2. WHEN sending notifications, THE Notification_System SHALL encrypt notification payloads
3. THE Notification_System SHALL provide different notification priorities based on circle membership
4. WHEN users are offline, THE Notification_System SHALL queue notifications for delivery when they reconnect
5. THE Notification_System SHALL allow users to configure notification preferences for each circle type

### Requirement 9: Mobile Application Architecture

**User Story:** As a developer, I want a well-structured Flutter application, so that the codebase is maintainable and follows security best practices.

#### Acceptance Criteria

1. THE Mobile_App SHALL use Flutter with Material 3 design system
2. THE Mobile_App SHALL implement Riverpod for state management
3. THE Mobile_App SHALL use abstract classes for common patterns (BaseRepository, BaseAPI)
4. THE Mobile_App SHALL validate all user inputs before processing
5. THE Mobile_App SHALL implement consistent error handling with standardized error responses

### Requirement 10: Backend API System

**User Story:** As a system administrator, I want a secure and scalable backend API, so that the application can handle multiple users while maintaining security.

#### Acceptance Criteria

1. THE Backend_API SHALL use Node.js/Express with PostgreSQL database
2. THE Backend_API SHALL implement authentication middleware for all protected endpoints
3. THE Backend_API SHALL validate and sanitize all incoming requests
4. THE Backend_API SHALL implement rate limiting to prevent abuse
5. THE Backend_API SHALL return consistent JSON responses with success, message, and code fields