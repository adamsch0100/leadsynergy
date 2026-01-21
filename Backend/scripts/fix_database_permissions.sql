-- =============================================
-- FIX DATABASE PERMISSIONS AND TRIGGERS
-- Run this in Supabase SQL Editor
-- =============================================

-- 1. Fix fub_browser_sessions table permissions
-- Disable RLS to allow service role full access
ALTER TABLE IF EXISTS fub_browser_sessions DISABLE ROW LEVEL SECURITY;

-- If the table doesn't exist, create it
CREATE TABLE IF NOT EXISTS fub_browser_sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    agent_id TEXT UNIQUE NOT NULL,
    session_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index if not exists
CREATE INDEX IF NOT EXISTS idx_fub_browser_sessions_agent_id ON fub_browser_sessions(agent_id);

-- Grant permissions to service role (Supabase's backend role)
GRANT ALL ON fub_browser_sessions TO service_role;
GRANT ALL ON fub_browser_sessions TO authenticated;
GRANT SELECT ON fub_browser_sessions TO anon;


-- 2. Fix ai_lead_profile_cache table trigger issue
-- The trigger references "updated_at" but the table/code uses "last_updated_at"

-- First, drop any problematic trigger
DROP TRIGGER IF EXISTS update_ai_lead_profile_cache_updated_at ON ai_lead_profile_cache;
DROP TRIGGER IF EXISTS set_updated_at ON ai_lead_profile_cache;

-- Create or replace the trigger function to use the correct column name
CREATE OR REPLACE FUNCTION update_last_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Check if ai_lead_profile_cache exists before adding trigger
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ai_lead_profile_cache') THEN
        -- Drop any existing trigger first
        DROP TRIGGER IF EXISTS update_last_updated_at ON ai_lead_profile_cache;

        -- Create the correct trigger
        CREATE TRIGGER update_last_updated_at
            BEFORE UPDATE ON ai_lead_profile_cache
            FOR EACH ROW
            EXECUTE FUNCTION update_last_updated_at_column();
    END IF;
END $$;

-- Disable RLS on ai_lead_profile_cache for service role access
ALTER TABLE IF EXISTS ai_lead_profile_cache DISABLE ROW LEVEL SECURITY;

-- Grant permissions
GRANT ALL ON ai_lead_profile_cache TO service_role;
GRANT ALL ON ai_lead_profile_cache TO authenticated;


-- 3. Ensure ai_conversations table has proper permissions
ALTER TABLE IF EXISTS ai_conversations DISABLE ROW LEVEL SECURITY;
GRANT ALL ON ai_conversations TO service_role;
GRANT ALL ON ai_conversations TO authenticated;


-- 4. Ensure ai_message_log table has proper permissions
ALTER TABLE IF EXISTS ai_message_log DISABLE ROW LEVEL SECURITY;
GRANT ALL ON ai_message_log TO service_role;
GRANT ALL ON ai_message_log TO authenticated;


-- 5. Ensure ai_agent_settings table has proper permissions
ALTER TABLE IF EXISTS ai_agent_settings DISABLE ROW LEVEL SECURITY;
GRANT ALL ON ai_agent_settings TO service_role;
GRANT ALL ON ai_agent_settings TO authenticated;


-- =============================================
-- VERIFICATION QUERIES
-- =============================================

-- Check fub_browser_sessions structure
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'fub_browser_sessions';

-- Check ai_lead_profile_cache structure
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'ai_lead_profile_cache';

-- List all triggers
SELECT trigger_name, event_object_table, action_statement
FROM information_schema.triggers
WHERE trigger_schema = 'public';
