-- ============================================================================
-- LEADSYNERGY FRONTEND SCHEMA FIX
-- ============================================================================
-- This migration fixes the schema to work with the Next.js frontend
-- The frontend expects UUID-based users table that matches Supabase Auth
--
-- IMPORTANT: Run this in Supabase SQL Editor
-- URL: https://supabase.com/dashboard/project/uavuasjvirgbhkszvzyy/sql
-- ============================================================================

-- ============================================================================
-- STEP 1: BACKUP EXISTING TABLES (if they use INTEGER keys)
-- ============================================================================

-- Backup users table if it exists and uses INTEGER keys
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'users' AND table_schema = 'public'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'users'
            AND column_name = 'id'
            AND data_type = 'integer'
        ) THEN
            EXECUTE 'ALTER TABLE users RENAME TO users_old_backup';
            RAISE NOTICE 'Backed up existing users table to users_old_backup';
        END IF;
    END IF;
END $$;

-- Backup leads table if it exists and uses INTEGER keys
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'leads' AND table_schema = 'public'
    ) THEN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'leads'
            AND column_name = 'id'
            AND data_type = 'integer'
        ) THEN
            EXECUTE 'ALTER TABLE leads RENAME TO leads_old_backup';
            RAISE NOTICE 'Backed up existing leads table to leads_old_backup';
        END IF;
    END IF;
END $$;

-- ============================================================================
-- STEP 2: CREATE ORGANIZATIONS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE,
    subscription_plan VARCHAR(50) DEFAULT 'basic',
    subscription_status VARCHAR(50) DEFAULT 'active',
    billing_email VARCHAR(255),
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);
CREATE INDEX IF NOT EXISTS idx_organizations_stripe_customer ON organizations(stripe_customer_id);

-- ============================================================================
-- STEP 3: CREATE NEW USERS TABLE (UUID-based, linked to Supabase Auth)
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL UNIQUE,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    full_name VARCHAR(255),
    phone VARCHAR(50),
    role VARCHAR(50) DEFAULT 'agent',
    is_active BOOLEAN DEFAULT TRUE,
    needs_setup BOOLEAN DEFAULT TRUE,
    subscription_status VARCHAR(50),
    fub_api_key TEXT,
    fub_terms_accepted BOOLEAN DEFAULT FALSE,
    fub_terms_accepted_at TIMESTAMPTZ,
    auto_add_note_on_search BOOLEAN DEFAULT TRUE,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- ============================================================================
-- STEP 4: CREATE ORGANIZATION_USERS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS organization_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'agent',
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_org_users_org_id ON organization_users(organization_id);
CREATE INDEX IF NOT EXISTS idx_org_users_user_id ON organization_users(user_id);

-- ============================================================================
-- STEP 5: CREATE LEADS TABLE (UUID-based)
-- ============================================================================

CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    source VARCHAR(100),
    status VARCHAR(50) DEFAULT 'new',
    notes TEXT,
    fub_person_id VARCHAR(255),
    fub_stage VARCHAR(100),
    platform_status VARCHAR(100),
    referral_fee_percent DECIMAL(5, 2),
    metadata JSONB DEFAULT '{}',
    organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL,
    assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);
CREATE INDEX IF NOT EXISTS idx_leads_fub_person_id ON leads(fub_person_id);
CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_org_id ON leads(organization_id);
CREATE INDEX IF NOT EXISTS idx_leads_assigned_to ON leads(assigned_to);

-- ============================================================================
-- STEP 6: SET UP ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;

-- Drop existing policies to avoid conflicts
DROP POLICY IF EXISTS "Service role bypass" ON organizations;
DROP POLICY IF EXISTS "Service role bypass" ON users;
DROP POLICY IF EXISTS "Service role bypass" ON organization_users;
DROP POLICY IF EXISTS "Service role bypass" ON leads;
DROP POLICY IF EXISTS "Users can view own profile" ON users;
DROP POLICY IF EXISTS "Users can insert own profile" ON users;
DROP POLICY IF EXISTS "Users can update own profile" ON users;

-- Service role bypasses RLS (for backend with service_role key)
CREATE POLICY "Service role bypass" ON organizations FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role bypass" ON users FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role bypass" ON organization_users FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role bypass" ON leads FOR ALL
    USING (auth.role() = 'service_role');

-- Authenticated users can view/update their own profile
CREATE POLICY "Users can view own profile" ON users FOR SELECT
    USING (id = auth.uid());

CREATE POLICY "Users can insert own profile" ON users FOR INSERT
    WITH CHECK (id = auth.uid());

CREATE POLICY "Users can update own profile" ON users FOR UPDATE
    USING (id = auth.uid());

-- ============================================================================
-- STEP 7: CREATE ADMIN USER AND ORGANIZATION
-- ============================================================================

-- Create the admin organization
INSERT INTO organizations (id, name, slug, subscription_plan, subscription_status, billing_email)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'SAA Homes',
    'saa-homes',
    'business',
    'active',
    'adam@saahomes.com'
) ON CONFLICT (slug) DO UPDATE SET
    subscription_status = 'active',
    updated_at = NOW();

-- Create the admin user (ID matches auth.users for adam@saahomes.com)
INSERT INTO users (id, email, first_name, last_name, full_name, role, is_active, needs_setup)
VALUES (
    '420314bc-0bc8-402f-aac6-12257ca2acf6',
    'adam@saahomes.com',
    'Adam',
    'Schwartz',
    'Adam Schwartz',
    'admin',
    TRUE,
    FALSE
) ON CONFLICT (id) DO UPDATE SET
    role = 'admin',
    full_name = 'Adam Schwartz',
    first_name = 'Adam',
    last_name = 'Schwartz',
    is_active = TRUE,
    needs_setup = FALSE,
    updated_at = NOW();

-- Link admin to organization
INSERT INTO organization_users (organization_id, user_id, role, is_primary)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    '420314bc-0bc8-402f-aac6-12257ca2acf6',
    'admin',
    TRUE
) ON CONFLICT (organization_id, user_id) DO UPDATE SET
    role = 'admin',
    is_primary = TRUE,
    updated_at = NOW();

-- ============================================================================
-- STEP 8: VERIFY SETUP
-- ============================================================================

SELECT 'Setup complete! Verifying...' as status;

SELECT 'Organizations' as table_name, count(*) as count FROM organizations
UNION ALL
SELECT 'Users', count(*) FROM users
UNION ALL
SELECT 'Organization Users', count(*) FROM organization_users;

SELECT 'Admin user:' as info, id, email, role FROM users WHERE email = 'adam@saahomes.com';

-- ============================================================================
-- DONE! You can now login with:
--   Email: adam@saahomes.com
--   Password: (whatever you set in Supabase Auth)
-- ============================================================================
