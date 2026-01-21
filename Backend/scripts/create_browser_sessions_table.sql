-- Create table for storing FUB browser sessions (Playwright cookies)
-- This allows sessions to persist across Railway deployments

CREATE TABLE IF NOT EXISTS fub_browser_sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    agent_id TEXT UNIQUE NOT NULL,
    session_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for fast lookups by agent_id
CREATE INDEX IF NOT EXISTS idx_fub_browser_sessions_agent_id ON fub_browser_sessions(agent_id);

-- Add comment
COMMENT ON TABLE fub_browser_sessions IS 'Stores Playwright browser session cookies for FUB automation. Persists across deployments.';
