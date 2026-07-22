-- Row-Level Security Policies for Circlo Safety Database
-- These policies ensure data isolation and access control

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE circles ENABLE ROW LEVEL SECURITY;
ALTER TABLE circle_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE push_tokens ENABLE ROW LEVEL SECURITY;

-- Create function to get current user ID from session
CREATE OR REPLACE FUNCTION current_user_id() RETURNS UUID AS $$
BEGIN
    RETURN NULLIF(current_setting('app.user_id', true), '')::UUID;
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Users table policies
-- Users can only see and modify their own data
CREATE POLICY users_own_data ON users
    FOR ALL
    USING (id = current_user_id());

-- Circles table policies
-- Owners can manage their circles
CREATE POLICY circles_owner_access ON circles
    FOR ALL
    USING (owner_id = current_user_id());

-- Members can view circles they belong to
CREATE POLICY circles_member_read ON circles
    FOR SELECT
    USING (
        id IN (
            SELECT circle_id FROM circle_members 
            WHERE user_id = current_user_id() 
            AND status = 'active'
        )
    );

-- Circle members table policies
-- Circle owners can manage members
CREATE POLICY circle_members_owner_access ON circle_members
    FOR ALL
    USING (
        circle_id IN (
            SELECT id FROM circles 
            WHERE owner_id = current_user_id()
        )
    );

-- Users can see their own memberships
CREATE POLICY circle_members_own_access ON circle_members
    FOR SELECT
    USING (user_id = current_user_id());

-- Users can update their own membership (for verification)
CREATE POLICY circle_members_own_update ON circle_members
    FOR UPDATE
    USING (user_id = current_user_id());

-- Alerts table policies
-- Users can manage their own alerts
CREATE POLICY alerts_own_access ON alerts
    FOR ALL
    USING (user_id = current_user_id());

-- Circle members can view alerts for users in their circles
CREATE POLICY alerts_circle_member_read ON alerts
    FOR SELECT
    USING (
        user_id IN (
            SELECT cm.user_id 
            FROM circle_members cm
            JOIN circles c ON cm.circle_id = c.id
            WHERE c.owner_id = current_user_id()
            AND cm.status = 'active'
        )
        OR
        user_id IN (
            SELECT c.owner_id
            FROM circles c
            JOIN circle_members cm ON c.id = cm.circle_id
            WHERE cm.user_id = current_user_id()
            AND cm.status = 'active'
        )
    );

-- Alert verifications policies
-- Users can create verifications for alerts they can see
CREATE POLICY alert_verifications_create ON alert_verifications
    FOR INSERT
    WITH CHECK (
        alert_id IN (
            SELECT id FROM alerts
            WHERE user_id IN (
                SELECT c.owner_id
                FROM circles c
                JOIN circle_members cm ON c.id = cm.circle_id
                WHERE cm.user_id = current_user_id()
                AND cm.status = 'active'
            )
        )
    );

-- Users can view verifications for alerts they can see
CREATE POLICY alert_verifications_read ON alert_verifications
    FOR SELECT
    USING (
        alert_id IN (
            SELECT id FROM alerts
            WHERE user_id = current_user_id()
            OR user_id IN (
                SELECT c.owner_id
                FROM circles c
                JOIN circle_members cm ON c.id = cm.circle_id
                WHERE cm.user_id = current_user_id()
                AND cm.status = 'active'
            )
        )
    );

-- Messages table policies
-- Users can send messages to alerts they're involved in
CREATE POLICY messages_create ON messages
    FOR INSERT
    WITH CHECK (
        sender_id = current_user_id()
        AND alert_id IN (
            SELECT id FROM alerts
            WHERE user_id = current_user_id()
            OR user_id IN (
                SELECT c.owner_id
                FROM circles c
                JOIN circle_members cm ON c.id = cm.circle_id
                WHERE cm.user_id = current_user_id()
                AND cm.status = 'active'
            )
        )
    );

-- Users can read messages for alerts they're involved in
CREATE POLICY messages_read ON messages
    FOR SELECT
    USING (
        alert_id IN (
            SELECT id FROM alerts
            WHERE user_id = current_user_id()
            OR user_id IN (
                SELECT c.owner_id
                FROM circles c
                JOIN circle_members cm ON c.id = cm.circle_id
                WHERE cm.user_id = current_user_id()
                AND cm.status = 'active'
            )
        )
    );

-- Audit logs policies
-- Only admins can view audit logs (handled at application level)
-- Users can see their own audit entries
CREATE POLICY audit_logs_own_read ON audit_logs
    FOR SELECT
    USING (user_id = current_user_id());

-- Push tokens policies
-- Users can only manage their own push tokens
CREATE POLICY push_tokens_own_access ON push_tokens
    FOR ALL
    USING (user_id = current_user_id());

-- Create function to automatically update last_active
CREATE OR REPLACE FUNCTION update_last_active()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE users SET last_active = NOW(), auto_delete_at = NOW() + INTERVAL '90 days'
    WHERE id = current_user_id();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Law enforcement access table RLS
ALTER TABLE law_enforcement_access ENABLE ROW LEVEL SECURITY;

-- Law enforcement can only see their own access records
CREATE POLICY law_enforcement_own_access ON law_enforcement_access
    FOR SELECT
    USING (
        -- Law enforcement officers can see their own access records
        officer_id = current_setting('app.officer_id', true)
        OR
        -- Alert owners can see who has accessed their alerts
        alert_id IN (
            SELECT id FROM alerts WHERE user_id = current_user_id()
        )
    );

-- Only system can grant law enforcement access (handled at application level)
CREATE POLICY law_enforcement_system_insert ON law_enforcement_access
    FOR INSERT
    WITH CHECK (
        -- Only allow insert if the current role is the service role
        current_setting('app.role', true) = 'service'
    );

-- Function to log law enforcement access
CREATE OR REPLACE FUNCTION log_law_enforcement_access()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_logs (
        user_id,
        action,
        resource_type,
        resource_id,
        details,
        ip_address
    ) VALUES (
        NULL, -- Law enforcement access is logged without user_id
        CASE 
            WHEN TG_OP = 'INSERT' THEN 'law_enforcement_access_granted'
            WHEN TG_OP = 'UPDATE' AND NEW.is_active = FALSE THEN 'law_enforcement_access_revoked'
            ELSE 'law_enforcement_access_updated'
        END,
        'law_enforcement_access',
        NEW.id,
        jsonb_build_object(
            'officer_id', NEW.officer_id,
            'alert_id', NEW.alert_id,
            'is_active', NEW.is_active,
            'operation', TG_OP
        ),
        inet_client_addr()
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to log law enforcement access
CREATE TRIGGER log_law_enforcement_access_trigger
    AFTER INSERT OR UPDATE ON law_enforcement_access
    FOR EACH ROW
    EXECUTE FUNCTION log_law_enforcement_access();

-- Function to log all data access for audit purposes
CREATE OR REPLACE FUNCTION log_data_access()
RETURNS TRIGGER AS $$
BEGIN
    -- Only log SELECT operations on sensitive tables
    IF TG_OP = 'SELECT' THEN
        INSERT INTO audit_logs (
            user_id,
            action,
            resource_type,
            resource_id,
            details
        ) VALUES (
            current_user_id(),
            'data_access',
            TG_TABLE_NAME,
            CASE 
                WHEN TG_TABLE_NAME = 'users' THEN NEW.id
                WHEN TG_TABLE_NAME = 'alerts' THEN NEW.id
                WHEN TG_TABLE_NAME = 'messages' THEN NEW.id
                ELSE NULL
            END,
            jsonb_build_object('table', TG_TABLE_NAME)
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to create audit log entry
CREATE OR REPLACE FUNCTION create_audit_log(
    p_user_id UUID,
    p_action VARCHAR(100),
    p_resource_type VARCHAR(50),
    p_resource_id UUID,
    p_details JSONB DEFAULT NULL,
    p_ip_address INET DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_audit_id UUID;
BEGIN
    INSERT INTO audit_logs (
        user_id,
        action,
        resource_type,
        resource_id,
        details,
        ip_address
    ) VALUES (
        p_user_id,
        p_action,
        p_resource_type,
        p_resource_id,
        p_details,
        p_ip_address
    )
    RETURNING id INTO v_audit_id;
    
    RETURN v_audit_id;
END;
$$ LANGUAGE plpgsql;

-- Function to automatically delete old data
CREATE OR REPLACE FUNCTION cleanup_expired_data()
RETURNS void AS $$
BEGIN
    -- Delete expired users
    DELETE FROM users WHERE auto_delete_at < NOW();
    
    -- Delete expired alerts
    DELETE FROM alerts WHERE auto_delete_at < NOW();
    
    -- Delete expired messages
    DELETE FROM messages WHERE auto_delete_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Create scheduled job for cleanup (requires pg_cron extension)
-- SELECT cron.schedule('cleanup-expired-data', '0 0 * * *', 'SELECT cleanup_expired_data()');
