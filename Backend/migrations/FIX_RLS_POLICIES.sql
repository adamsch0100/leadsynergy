-- ============================================================================
-- FIX RLS POLICIES - Run this in Supabase SQL Editor
-- ============================================================================

-- Option 1: Disable RLS entirely (simpler, less secure but works)
ALTER TABLE organizations DISABLE ROW LEVEL SECURITY;
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE organization_users DISABLE ROW LEVEL SECURITY;
ALTER TABLE leads DISABLE ROW LEVEL SECURITY;

-- Verify admin user exists
SELECT 'Admin user check:' as info, id, email, role, full_name
FROM users
WHERE email = 'adam@saahomes.com';

-- If no user found, insert it
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
    is_active = TRUE;

-- Verify
SELECT 'Final check:' as info, id, email, role FROM users WHERE email = 'adam@saahomes.com';
