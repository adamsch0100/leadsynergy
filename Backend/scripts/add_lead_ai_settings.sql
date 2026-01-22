-- Create table for per-lead AI auto-respond settings
-- This allows granular control over which leads receive AI responses

CREATE TABLE IF NOT EXISTS lead_ai_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fub_person_id VARCHAR(255) NOT NULL,
    organization_id UUID NOT NULL,
    user_id UUID NOT NULL,

    -- AI control
    ai_enabled BOOLEAN DEFAULT true,

    -- Metadata
    enabled_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    disabled_at TIMESTAMP WITH TIME ZONE,
    enabled_by VARCHAR(255), -- User ID who enabled it
    reason VARCHAR(50), -- 'new_lead', 'revival', 'manual', etc.

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    UNIQUE(fub_person_id, organization_id),
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_lead_ai_settings_person ON lead_ai_settings(fub_person_id);
CREATE INDEX IF NOT EXISTS idx_lead_ai_settings_org ON lead_ai_settings(organization_id);
CREATE INDEX IF NOT EXISTS idx_lead_ai_settings_user ON lead_ai_settings(user_id);
CREATE INDEX IF NOT EXISTS idx_lead_ai_settings_enabled ON lead_ai_settings(ai_enabled);

-- Add RLS policies
ALTER TABLE lead_ai_settings ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view their own organization's lead AI settings
CREATE POLICY "Users can view org lead AI settings"
    ON lead_ai_settings FOR SELECT
    USING (
        organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    );

-- Policy: Users can manage their own organization's lead AI settings
CREATE POLICY "Users can manage org lead AI settings"
    ON lead_ai_settings FOR ALL
    USING (
        organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    );

-- Grant permissions
GRANT ALL ON lead_ai_settings TO authenticated;
GRANT ALL ON lead_ai_settings TO service_role;

-- Add comment
COMMENT ON TABLE lead_ai_settings IS 'Per-lead AI auto-respond settings. Controls which specific leads receive AI responses.';
