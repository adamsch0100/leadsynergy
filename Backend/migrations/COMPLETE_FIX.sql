-- ============================================================================
-- COMPLETE FIX - Run this ENTIRE script in Supabase SQL Editor
-- ============================================================================

-- Step 1: Check what tables exist
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

-- Step 2: Disable RLS on all relevant tables
DO $$
DECLARE
    tbl text;
BEGIN
    FOR tbl IN SELECT table_name FROM information_schema.tables
               WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    LOOP
        EXECUTE format('ALTER TABLE %I DISABLE ROW LEVEL SECURITY', tbl);
        RAISE NOTICE 'Disabled RLS on %', tbl;
    END LOOP;
END $$;

-- Step 3: Grant permissions to authenticated and service_role
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon;
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT USAGE ON SCHEMA public TO service_role;
GRANT USAGE ON SCHEMA public TO anon;

-- Step 4: Ensure users table has correct structure and data
-- First check if table exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users' AND table_schema = 'public') THEN
        -- Create users table
        CREATE TABLE public.users (
            id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
            email VARCHAR(255) NOT NULL UNIQUE,
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            full_name VARCHAR(255),
            phone VARCHAR(50),
            role VARCHAR(50) DEFAULT 'agent',
            is_active BOOLEAN DEFAULT TRUE,
            needs_setup BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        RAISE NOTICE 'Created users table';
    END IF;
END $$;

-- Step 5: Insert/update admin user
INSERT INTO public.users (id, email, first_name, last_name, full_name, role, is_active, needs_setup)
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
    is_active = TRUE,
    needs_setup = FALSE,
    updated_at = NOW();

-- Step 6: Create organizations table if needed
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'organizations' AND table_schema = 'public') THEN
        CREATE TABLE public.organizations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            slug VARCHAR(255) UNIQUE,
            subscription_plan VARCHAR(50) DEFAULT 'basic',
            subscription_status VARCHAR(50) DEFAULT 'active',
            billing_email VARCHAR(255),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        RAISE NOTICE 'Created organizations table';
    END IF;
END $$;

-- Step 7: Create organization_users table if needed
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'organization_users' AND table_schema = 'public') THEN
        CREATE TABLE public.organization_users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            role VARCHAR(50) DEFAULT 'agent',
            is_primary BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(organization_id, user_id)
        );
        RAISE NOTICE 'Created organization_users table';
    END IF;
END $$;

-- Step 8: Re-grant permissions after creating tables
GRANT ALL ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO anon;

-- Step 9: Verify
SELECT 'VERIFICATION' as step;
SELECT id, email, role, is_active FROM public.users WHERE email = 'adam@saahomes.com';
