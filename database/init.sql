-- Circlo Safety Database Schema
-- PostgreSQL with Row-Level Security

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create custom types
CREATE TYPE circle_type AS ENUM ('inner', 'community', 'professional');
CREATE TYPE alert_type AS ENUM ('missing', 'emergency', 'check_in');
CREATE TYPE alert_status AS ENUM ('pending', 'verified', 'escalated', 'resolved');
CREATE TYPE member_status AS ENUM ('pending', 'active', 'removed');

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_hash VARCHAR(64) UNIQUE NOT NULL,
    name_encrypted TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    auto_delete_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '90 days')
);

-- Create index for phone_hash lookups
CREATE INDEX idx_users_phone_hash ON users(phone_hash);

-- Circles table
CREATE TABLE circles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type circle_type NOT NULL,
    name_encrypted TEXT NOT NULL,
    max_members INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT valid_max_members CHECK (
        (type = 'inner' AND max_members BETWEEN 3 AND 5) OR
        (type = 'community' AND max_members BETWEEN 15 AND 30) OR
        (type = 'professional' AND max_members >= 1)
    )
);

-- Create index for owner lookups
CREATE INDEX idx_circles_owner_id ON circles(owner_id);

-- Circle members table
CREATE TABLE circle_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    circle_id UUID NOT NULL REFERENCES circles(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status member_status DEFAULT 'pending',
    invited_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    verified_at TIMESTAMP WITH TIME ZONE,
    mutual_verified BOOLEAN DEFAULT FALSE,
    UNIQUE(circle_id, user_id)
);

-- Create indexes for member lookups
CREATE INDEX idx_circle_members_circle_id ON circle_members(circle_id);
CREATE INDEX idx_circle_members_user_id ON circle_members(user_id);

-- Alerts table
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type alert_type NOT NULL,
    status alert_status DEFAULT 'pending',
    verification_count INTEGER DEFAULT 0,
    required_verifications INTEGER DEFAULT 2,
    escalation_level INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    escalated_at TIMESTAMP WITH TIME ZONE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    auto_delete_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '90 days')
);

-- Create indexes for alert lookups
CREATE INDEX idx_alerts_user_id ON alerts(user_id);
CREATE INDEX idx_alerts_status ON alerts(status);

-- Alert verifications table
CREATE TABLE alert_verifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    verifier_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    verified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(alert_id, verifier_id)
);

-- Create index for verification lookups
CREATE INDEX idx_alert_verifications_alert_id ON alert_verifications(alert_id);

-- Messages table (for encrypted communications during alerts)
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    sender_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content_encrypted TEXT NOT NULL,
    iv TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    auto_delete_at TIMESTAMP WITH TIME ZONE DEFAULT (NOW() + INTERVAL '90 days')
);

-- Create indexes for message lookups
CREATE INDEX idx_messages_alert_id ON messages(alert_id);
CREATE INDEX idx_messages_sender_id ON messages(sender_id);

-- Audit log table for law enforcement access
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for audit log lookups
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- Push notification tokens table
CREATE TABLE push_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token TEXT NOT NULL,
    platform VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, token)
);

-- Create index for push token lookups
CREATE INDEX idx_push_tokens_user_id ON push_tokens(user_id);

-- Law enforcement access table
CREATE TABLE law_enforcement_access (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    officer_id VARCHAR(100) NOT NULL,
    officer_name_encrypted TEXT NOT NULL,
    badge_number_hash VARCHAR(64) NOT NULL,
    department_encrypted TEXT NOT NULL,
    alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    access_granted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    access_revoked_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create index for law enforcement access lookups
CREATE INDEX idx_law_enforcement_access_alert_id ON law_enforcement_access(alert_id);
CREATE INDEX idx_law_enforcement_access_officer_id ON law_enforcement_access(officer_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_circles_updated_at
    BEFORE UPDATE ON circles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_push_tokens_updated_at
    BEFORE UPDATE ON push_tokens
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Function to reset auto_delete_at on user activity
CREATE OR REPLACE FUNCTION reset_user_auto_delete()
RETURNS TRIGGER AS $$
BEGIN
    NEW.auto_delete_at = NOW() + INTERVAL '90 days';
    NEW.last_active = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to reset auto_delete_at when user is active
CREATE TRIGGER reset_user_auto_delete_trigger
    BEFORE UPDATE ON users
    FOR EACH ROW
    WHEN (OLD.last_active IS DISTINCT FROM NEW.last_active)
    EXECUTE FUNCTION reset_user_auto_delete();

-- Function to automatically delete expired data
CREATE OR REPLACE FUNCTION cleanup_expired_data()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER := 0;
    temp_count INTEGER;
BEGIN
    -- Delete expired messages first (due to foreign key constraints)
    DELETE FROM messages WHERE auto_delete_at < NOW();
    GET DIAGNOSTICS temp_count = ROW_COUNT;
    deleted_count := deleted_count + temp_count;
    
    -- Delete expired alerts
    DELETE FROM alerts WHERE auto_delete_at < NOW();
    GET DIAGNOSTICS temp_count = ROW_COUNT;
    deleted_count := deleted_count + temp_count;
    
    -- Delete expired users (cascades to circles, memberships, etc.)
    DELETE FROM users WHERE auto_delete_at < NOW();
    GET DIAGNOSTICS temp_count = ROW_COUNT;
    deleted_count := deleted_count + temp_count;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to set auto_delete_at on alert resolution
CREATE OR REPLACE FUNCTION set_alert_auto_delete_on_resolution()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'resolved' AND OLD.status != 'resolved' THEN
        NEW.resolved_at = NOW();
        NEW.auto_delete_at = NOW() + INTERVAL '90 days';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to set auto_delete_at when alert is resolved
CREATE TRIGGER alert_resolution_trigger
    BEFORE UPDATE ON alerts
    FOR EACH ROW
    EXECUTE FUNCTION set_alert_auto_delete_on_resolution();

-- Function to cascade auto_delete_at to messages when alert is resolved
CREATE OR REPLACE FUNCTION cascade_alert_auto_delete_to_messages()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'resolved' AND OLD.status != 'resolved' THEN
        UPDATE messages 
        SET auto_delete_at = NEW.auto_delete_at
        WHERE alert_id = NEW.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to cascade auto_delete_at to messages
CREATE TRIGGER cascade_alert_auto_delete_trigger
    AFTER UPDATE ON alerts
    FOR EACH ROW
    EXECUTE FUNCTION cascade_alert_auto_delete_to_messages();


-- ==================== Notification System Tables ====================
-- Requirements: 8.1, 8.2, 8.3, 8.4, 8.5

-- Notification priority enum
CREATE TYPE notification_priority AS ENUM ('critical', 'high', 'normal', 'low');

-- Notification status enum
CREATE TYPE notification_status AS ENUM ('pending', 'sent', 'delivered', 'failed', 'expired');

-- Notification type enum
CREATE TYPE notification_type AS ENUM (
    'alert_created', 'alert_verified', 'alert_escalated', 'alert_resolved',
    'verification_request', 'check_request', 'circle_invite', 'circle_update',
    'message', 'system'
);

-- Device tokens table (for FCM registration)
CREATE TABLE device_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(512) NOT NULL UNIQUE,
    platform VARCHAR(20) NOT NULL CHECK (platform IN ('ios', 'android', 'web')),
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for device token lookups
CREATE INDEX idx_device_tokens_user_id ON device_tokens(user_id);
CREATE INDEX idx_device_tokens_token ON device_tokens(token);

-- Trigger for device_tokens updated_at
CREATE TRIGGER update_device_tokens_updated_at
    BEFORE UPDATE ON device_tokens
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Notifications table (with encrypted content)
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Encrypted content
    title_encrypted TEXT NOT NULL,
    body_encrypted TEXT NOT NULL,
    data_encrypted TEXT,
    iv VARCHAR(32) NOT NULL,
    
    -- Notification metadata
    type notification_type NOT NULL,
    priority notification_priority DEFAULT 'normal',
    status notification_status DEFAULT 'pending',
    
    -- Related entities
    alert_id UUID REFERENCES alerts(id) ON DELETE SET NULL,
    circle_id UUID REFERENCES circles(id) ON DELETE SET NULL,
    
    -- Delivery tracking
    fcm_message_id VARCHAR(255),
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    scheduled_at TIMESTAMP WITH TIME ZONE,
    sent_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for notification lookups
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_status ON notifications(status);
CREATE INDEX idx_notifications_alert_id ON notifications(alert_id);
CREATE INDEX idx_notifications_created_at ON notifications(created_at);

-- Notification preferences table
CREATE TABLE notification_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    
    -- Preferences by circle type
    inner_circle_enabled BOOLEAN DEFAULT TRUE,
    community_circle_enabled BOOLEAN DEFAULT TRUE,
    professional_circle_enabled BOOLEAN DEFAULT TRUE,
    
    -- Notification type preferences
    alert_notifications BOOLEAN DEFAULT TRUE,
    message_notifications BOOLEAN DEFAULT TRUE,
    circle_notifications BOOLEAN DEFAULT TRUE,
    system_notifications BOOLEAN DEFAULT TRUE,
    
    -- Quiet hours
    quiet_hours_enabled BOOLEAN DEFAULT FALSE,
    quiet_hours_start VARCHAR(5),  -- HH:MM format
    quiet_hours_end VARCHAR(5),    -- HH:MM format
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for notification preferences
CREATE INDEX idx_notification_preferences_user_id ON notification_preferences(user_id);

-- Trigger for notification_preferences updated_at
CREATE TRIGGER update_notification_preferences_updated_at
    BEFORE UPDATE ON notification_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Notification queue table (for offline users)
CREATE TABLE notification_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    notification_id UUID NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
    device_token_id UUID NOT NULL REFERENCES device_tokens(id) ON DELETE CASCADE,
    attempts INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP WITH TIME ZONE,
    next_attempt_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(notification_id, device_token_id)
);

-- Create indexes for notification queue
CREATE INDEX idx_notification_queue_next_attempt ON notification_queue(next_attempt_at);
CREATE INDEX idx_notification_queue_notification_id ON notification_queue(notification_id);


-- ==================== Law Enforcement Portal Tables ====================
-- Requirements: 6.1, 6.2, 6.3, 6.4, 6.5

-- Law enforcement access status enum
CREATE TYPE le_access_status AS ENUM ('pending', 'approved', 'denied', 'revoked');

-- Law enforcement officers table
CREATE TABLE law_enforcement_officers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    badge_number_hash VARCHAR(64) UNIQUE NOT NULL,
    name_encrypted TEXT NOT NULL,
    department_encrypted TEXT NOT NULL,
    email_hash VARCHAR(64) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE
);

-- Create indexes for law enforcement officer lookups
CREATE INDEX idx_le_officers_badge_hash ON law_enforcement_officers(badge_number_hash);
CREATE INDEX idx_le_officers_email_hash ON law_enforcement_officers(email_hash);

-- Trigger for law_enforcement_officers updated_at
CREATE TRIGGER update_le_officers_updated_at
    BEFORE UPDATE ON law_enforcement_officers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Law enforcement case access table
CREATE TABLE le_case_access (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    officer_id UUID NOT NULL REFERENCES law_enforcement_officers(id) ON DELETE CASCADE,
    alert_id UUID NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    status le_access_status DEFAULT 'pending',
    access_reason_encrypted TEXT NOT NULL,
    iv VARCHAR(32) NOT NULL,
    granted_at TIMESTAMP WITH TIME ZONE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(officer_id, alert_id)
);

-- Create indexes for case access lookups
CREATE INDEX idx_le_case_access_officer_id ON le_case_access(officer_id);
CREATE INDEX idx_le_case_access_alert_id ON le_case_access(alert_id);
CREATE INDEX idx_le_case_access_status ON le_case_access(status);

-- Law enforcement audit logs table
CREATE TABLE le_audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    officer_id UUID REFERENCES law_enforcement_officers(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID,
    details_encrypted TEXT,
    iv VARCHAR(32),
    ip_address VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for audit log lookups
CREATE INDEX idx_le_audit_logs_officer_id ON le_audit_logs(officer_id);
CREATE INDEX idx_le_audit_logs_created_at ON le_audit_logs(created_at);
CREATE INDEX idx_le_audit_logs_resource ON le_audit_logs(resource_type, resource_id);

-- Function to automatically revoke LE access when alert is resolved
CREATE OR REPLACE FUNCTION revoke_le_access_on_resolution()
RETURNS TRIGGER AS $
BEGIN
    IF NEW.status = 'resolved' AND OLD.status != 'resolved' THEN
        UPDATE le_case_access 
        SET status = 'revoked', revoked_at = NOW()
        WHERE alert_id = NEW.id AND status = 'approved';
    END IF;
    RETURN NEW;
END;
$ LANGUAGE plpgsql;

-- Trigger to revoke LE access when alert is resolved
CREATE TRIGGER revoke_le_access_on_alert_resolution
    AFTER UPDATE ON alerts
    FOR EACH ROW
    EXECUTE FUNCTION revoke_le_access_on_resolution();
