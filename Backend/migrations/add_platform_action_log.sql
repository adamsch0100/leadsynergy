-- Migration: Add platform_action_log table
-- Created for LeadSynergy - tracks referral platform actions from FUB embedded app

-- Platform action log table
CREATE TABLE IF NOT EXISTS platform_action_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    platform VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    old_status VARCHAR(100),
    new_status VARCHAR(100),
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for querying by lead
CREATE INDEX IF NOT EXISTS idx_platform_action_log_lead_id ON platform_action_log(lead_id);

-- Index for querying by platform
CREATE INDEX IF NOT EXISTS idx_platform_action_log_platform ON platform_action_log(platform);

-- Index for querying by action type
CREATE INDEX IF NOT EXISTS idx_platform_action_log_action ON platform_action_log(action);

-- Index for querying by created date
CREATE INDEX IF NOT EXISTS idx_platform_action_log_created_at ON platform_action_log(created_at DESC);

-- Commission submissions table (if not exists)
CREATE TABLE IF NOT EXISTS commission_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    fub_person_id VARCHAR(50),
    platform VARCHAR(50),
    sale_price DECIMAL(12, 2),
    commission_amount DECIMAL(12, 2),
    fee_percent DECIMAL(5, 2),
    close_date DATE,
    notes TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for commission queries
CREATE INDEX IF NOT EXISTS idx_commission_submissions_lead_id ON commission_submissions(lead_id);
CREATE INDEX IF NOT EXISTS idx_commission_submissions_user_id ON commission_submissions(user_id);
CREATE INDEX IF NOT EXISTS idx_commission_submissions_status ON commission_submissions(status);
CREATE INDEX IF NOT EXISTS idx_commission_submissions_close_date ON commission_submissions(close_date);

-- Add auto-enhancement settings to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_enhance_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_enhance_phone BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_enhance_email BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_enhance_credit_limit INTEGER DEFAULT 10;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_add_phone_to_fub_on_manual_enhance BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_add_email_to_fub_on_manual_enhance BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_add_note_on_search BOOLEAN DEFAULT TRUE;

-- Add FUB terms acceptance fields if not exist
ALTER TABLE users ADD COLUMN IF NOT EXISTS fub_terms_accepted BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS fub_terms_accepted_at TIMESTAMP WITH TIME ZONE;

-- FUB terms acceptance audit table
CREATE TABLE IF NOT EXISTS fub_terms_acceptance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    accepted BOOLEAN DEFAULT FALSE,
    accepted_at TIMESTAMP WITH TIME ZONE,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fub_terms_acceptance_user_id ON fub_terms_acceptance(user_id);

-- Enable RLS on new tables
ALTER TABLE platform_action_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE commission_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE fub_terms_acceptance ENABLE ROW LEVEL SECURITY;

-- RLS Policies for platform_action_log
CREATE POLICY IF NOT EXISTS "Users can view their own action logs"
    ON platform_action_log FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY IF NOT EXISTS "Users can insert their own action logs"
    ON platform_action_log FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- RLS Policies for commission_submissions
CREATE POLICY IF NOT EXISTS "Users can view their own commissions"
    ON commission_submissions FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY IF NOT EXISTS "Users can insert their own commissions"
    ON commission_submissions FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY IF NOT EXISTS "Users can update their own commissions"
    ON commission_submissions FOR UPDATE
    USING (user_id = auth.uid());
