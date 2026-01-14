-- ============================================================================
-- LEADSYNERGY MIGRATION FOR EXISTING DATABASE
-- ============================================================================
-- This migration adds LeadSynergy features to an EXISTING database
-- that uses INTEGER primary keys (not UUIDs)
-- ============================================================================

-- ============================================================================
-- 0. SCHEMA MIGRATIONS TRACKING TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    version VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 1. ADD MISSING COLUMNS TO USERS TABLE
-- ============================================================================
ALTER TABLE users ADD COLUMN IF NOT EXISTS name VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'agent';
ALTER TABLE users ADD COLUMN IF NOT EXISTS needs_setup BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS fub_terms_accepted BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS fub_terms_accepted_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_add_note_on_search BOOLEAN DEFAULT TRUE;

-- ============================================================================
-- 2. ADD MISSING COLUMNS TO LEADS TABLE
-- ============================================================================
ALTER TABLE leads ADD COLUMN IF NOT EXISTS fub_person_id VARCHAR(255);
ALTER TABLE leads ADD COLUMN IF NOT EXISTS fub_stage VARCHAR(100);
ALTER TABLE leads ADD COLUMN IF NOT EXISTS platform_status VARCHAR(100);
ALTER TABLE leads ADD COLUMN IF NOT EXISTS referral_fee_percent DECIMAL(5, 2);
ALTER TABLE leads ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- Index for fub_person_id lookups
CREATE INDEX IF NOT EXISTS idx_leads_fub_person_id ON leads(fub_person_id);

-- ============================================================================
-- 3. LEAD SOURCE SETTINGS TABLE (NEW)
-- Configuration for each lead source per user
-- ============================================================================
CREATE TABLE IF NOT EXISTS lead_source_settings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    source_name VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    auto_discovered BOOLEAN DEFAULT FALSE,
    username VARCHAR(255),
    password_encrypted TEXT,
    sync_interval_days INTEGER,
    last_sync_at TIMESTAMPTZ,
    next_sync_at TIMESTAMPTZ,
    fub_stage_mapping JSONB DEFAULT '{}',
    assignment_strategy VARCHAR(50) DEFAULT 'specific',
    assignment_rules JSONB DEFAULT '{}',
    referral_fee_percent DECIMAL(5, 2) DEFAULT 0,
    options JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    same_status_note TEXT DEFAULT 'Same as previous update. Continuing to communicate and assist the referral as best as possible.',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, source_name)
);

-- Indexes for lead_source_settings
CREATE INDEX IF NOT EXISTS idx_lead_source_settings_user_id ON lead_source_settings(user_id);
CREATE INDEX IF NOT EXISTS idx_lead_source_settings_source_name ON lead_source_settings(source_name);
CREATE INDEX IF NOT EXISTS idx_lead_source_settings_is_active ON lead_source_settings(is_active);

-- ============================================================================
-- 4. ADD MISSING COLUMNS TO LOOKUP_HISTORY
-- ============================================================================
ALTER TABLE lookup_history ADD COLUMN IF NOT EXISTS fub_person_id VARCHAR(255);
ALTER TABLE lookup_history ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

-- ============================================================================
-- 5. ADD MISSING COLUMNS TO TICKET_NOTES
-- ============================================================================
ALTER TABLE ticket_notes ADD COLUMN IF NOT EXISTS is_internal BOOLEAN DEFAULT FALSE;

-- ============================================================================
-- 6. PLATFORM ACTION LOG TABLE (NEW)
-- Tracks actions taken on referral platforms from FUB embedded app
-- ============================================================================
CREATE TABLE IF NOT EXISTS platform_action_log (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    platform VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    old_status VARCHAR(100),
    new_status VARCHAR(100),
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for platform_action_log
CREATE INDEX IF NOT EXISTS idx_platform_action_log_lead_id ON platform_action_log(lead_id);
CREATE INDEX IF NOT EXISTS idx_platform_action_log_platform ON platform_action_log(platform);
CREATE INDEX IF NOT EXISTS idx_platform_action_log_action ON platform_action_log(action);
CREATE INDEX IF NOT EXISTS idx_platform_action_log_created_at ON platform_action_log(created_at DESC);

-- ============================================================================
-- 7. COMMISSION SUBMISSIONS TABLE (NEW)
-- Tracks commission submissions for closed deals
-- ============================================================================
CREATE TABLE IF NOT EXISTS commission_submissions (
    id SERIAL PRIMARY KEY,
    lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    fub_person_id VARCHAR(50),
    platform VARCHAR(50),
    sale_price DECIMAL(12, 2),
    commission_amount DECIMAL(12, 2),
    fee_percent DECIMAL(5, 2),
    close_date DATE,
    notes TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for commission_submissions
CREATE INDEX IF NOT EXISTS idx_commission_submissions_lead_id ON commission_submissions(lead_id);
CREATE INDEX IF NOT EXISTS idx_commission_submissions_user_id ON commission_submissions(user_id);
CREATE INDEX IF NOT EXISTS idx_commission_submissions_status ON commission_submissions(status);
CREATE INDEX IF NOT EXISTS idx_commission_submissions_close_date ON commission_submissions(close_date);

-- ============================================================================
-- 8. FUB TERMS ACCEPTANCE TABLE (NEW)
-- Audit trail for FUB terms acceptance
-- ============================================================================
CREATE TABLE IF NOT EXISTS fub_terms_acceptance (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    accepted BOOLEAN DEFAULT FALSE,
    accepted_at TIMESTAMPTZ,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fub_terms_acceptance_user_id ON fub_terms_acceptance(user_id);

-- ============================================================================
-- 9. UPDATE CREDIT BUNDLES TO LEADSYNERGY PRICING
-- ============================================================================
-- Update existing subscription bundles to match LeadSynergy pricing

UPDATE credit_bundles SET
    name = 'Solo Agent',
    description = 'For individual agents. 3 referral platforms, unlimited lead sync, 25 enhancements, 1 criminal, 50 DNC/month.',
    price = 7900,
    enhancement_credits = 25,
    criminal_credits = 1,
    dnc_credits = 50,
    bundle_type = 'subscription'
WHERE bundle_type = 'subscription' AND (id = 1 OR name ILIKE '%essential%' OR name ILIKE '%solo%');

UPDATE credit_bundles SET
    name = 'Team',
    description = 'For small teams (up to 5). All 5 platforms, commission tracking, 100 enhancements, 3 criminal, 150 DNC/month.',
    price = 14900,
    enhancement_credits = 100,
    criminal_credits = 3,
    dnc_credits = 150,
    bundle_type = 'subscription'
WHERE bundle_type = 'subscription' AND (id = 2 OR name ILIKE '%professional%' OR name ILIKE '%team%');

UPDATE credit_bundles SET
    name = 'Brokerage',
    description = 'For brokerages (up to 15). All features, credit allocation, analytics, 300 enhancements, 8 criminal, 400 DNC/month.',
    price = 29900,
    enhancement_credits = 300,
    criminal_credits = 8,
    dnc_credits = 400,
    bundle_type = 'subscription'
WHERE bundle_type = 'subscription' AND (id = 3 OR name ILIKE '%pro plus%' OR name ILIKE '%brokerage%');

UPDATE credit_bundles SET
    name = 'Enterprise',
    description = 'For large brokerages. Unlimited members, API access, dedicated support, 1000+ enhancements, 25+ criminal, 1500+ DNC/month.',
    price = 0,
    enhancement_credits = 1000,
    criminal_credits = 25,
    dnc_credits = 1500,
    bundle_type = 'subscription'
WHERE bundle_type = 'subscription' AND (id = 4 OR name ILIKE '%enterprise%');

-- ============================================================================
-- 10. CREATE OR UPDATE ADMIN USER
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE email = 'adam@saahomes.com') THEN
        INSERT INTO users (
            email,
            password_hash,
            is_active,
            user_type,
            is_admin,
            created_at,
            updated_at,
            role,
            subscription_status
        ) VALUES (
            'adam@saahomes.com',
            -- bcrypt hash for 'Vitzer0100!' - change password after first login
            '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.dTHRVQXzGKqaC.',
            TRUE,
            'admin',
            TRUE,
            NOW(),
            NOW(),
            'admin',
            'active'
        );
        RAISE NOTICE 'Admin user created: adam@saahomes.com';
    ELSE
        UPDATE users SET
            is_admin = TRUE,
            user_type = 'admin',
            role = 'admin',
            subscription_status = 'active'
        WHERE email = 'adam@saahomes.com';
        RAISE NOTICE 'Existing user updated to admin: adam@saahomes.com';
    END IF;
END $$;

-- ============================================================================
-- 11. RECORD MIGRATION COMPLETION
-- ============================================================================
INSERT INTO schema_migrations (version, description)
VALUES (
    '20260109_leadsynergy_migration',
    'LeadSynergy migration: lead_source_settings, platform_action_log, commission_submissions, fub_terms_acceptance, user/lead extensions'
) ON CONFLICT (version) DO NOTHING;

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- To verify, run:
-- SELECT * FROM schema_migrations ORDER BY applied_at DESC;
-- SELECT * FROM lead_source_settings LIMIT 5;
-- SELECT * FROM users WHERE email = 'adam@saahomes.com';
-- ============================================================================
