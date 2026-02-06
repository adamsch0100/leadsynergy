-- Fix ai_scheduled_followups table constraints
-- The original CHECK constraints only allowed 5 message types and 2 channels,
-- but the follow-up system uses 15+ message types and 4 channels (sms, email, rvm, call).
-- Run this in Supabase SQL Editor.

-- Drop the restrictive message_type check constraint
ALTER TABLE ai_scheduled_followups DROP CONSTRAINT IF EXISTS ai_followups_message_type_check;

-- Drop the restrictive channel check constraint (only allowed sms/email, but rvm/call also needed)
ALTER TABLE ai_scheduled_followups DROP CONSTRAINT IF EXISTS ai_followups_channel_check;

-- Add a more permissive channel check (sms, email, rvm, call)
ALTER TABLE ai_scheduled_followups ADD CONSTRAINT ai_followups_channel_check
    CHECK (channel IN ('sms', 'email', 'rvm', 'call'));

-- Grant permissions (in case they're missing)
GRANT ALL ON ai_scheduled_followups TO authenticated;
GRANT ALL ON ai_scheduled_followups TO service_role;

-- Enable RLS
ALTER TABLE ai_scheduled_followups ENABLE ROW LEVEL SECURITY;

-- Create permissive RLS policy
DO $$ BEGIN
    CREATE POLICY "Allow full access to ai_scheduled_followups"
    ON ai_scheduled_followups
    FOR ALL
    USING (true)
    WITH CHECK (true);
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
