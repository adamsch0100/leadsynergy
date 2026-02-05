-- Fix permissions for proactive_outreach_log table
-- Run this in Supabase SQL Editor

-- Grant full access to authenticated users
GRANT ALL ON proactive_outreach_log TO authenticated;
GRANT ALL ON proactive_outreach_log TO service_role;

-- Grant access to the analytics view
GRANT SELECT ON proactive_outreach_analytics TO authenticated;
GRANT SELECT ON proactive_outreach_analytics TO service_role;

-- Enable RLS (Row Level Security) on the table
ALTER TABLE proactive_outreach_log ENABLE ROW LEVEL SECURITY;

-- Create policy to allow service_role and authenticated to do everything
CREATE POLICY "Allow full access to proactive_outreach_log"
ON proactive_outreach_log
FOR ALL
USING (true)
WITH CHECK (true);

-- Grant usage on the function
GRANT EXECUTE ON FUNCTION update_proactive_outreach_response() TO authenticated;
GRANT EXECUTE ON FUNCTION update_proactive_outreach_response() TO service_role;
