-- Migration: Add Proactive Outreach System Tables and Columns
-- Purpose: Track proactive AI outreach when leads are enabled
-- Date: 2026-02-05

-- =========================================
-- 1. CREATE proactive_outreach_log TABLE
-- =========================================
-- Logs every proactive outreach attempt with full context

CREATE TABLE IF NOT EXISTS proactive_outreach_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fub_person_id TEXT NOT NULL,
    organization_id UUID NOT NULL,

    -- Trigger context
    trigger_reason TEXT NOT NULL, -- 'new_lead_ai_enabled', 'manual_enable', 'revival', 'backfill'
    enable_type TEXT, -- 'auto' or 'manual'
    triggered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Lead analysis results
    lead_stage TEXT, -- 'NEW', 'DORMANT', 'WARM', 'COLD', 'RETURNING'
    days_since_last_contact INTEGER,
    strategy_used TEXT, -- 'enthusiastic_intro', 'soft_reconnection', 'value_first', 'continuity'
    prior_topics_discussed TEXT[], -- Array of topics like ['budget', 'timeline']
    questions_already_asked TEXT[], -- Array of questions like ['preapproval', 'timeline']

    -- Outreach content
    sms_sent BOOLEAN DEFAULT FALSE,
    email_sent BOOLEAN DEFAULT FALSE,
    sms_preview TEXT, -- First 200 chars for quick review
    email_subject TEXT,

    -- Delivery timing
    sent_at TIMESTAMP WITH TIME ZONE,
    queued_for TIMESTAMP WITH TIME ZONE, -- If outside TCPA hours

    -- Response tracking
    lead_responded BOOLEAN DEFAULT FALSE,
    responded_at TIMESTAMP WITH TIME ZONE,
    response_time_minutes INTEGER,

    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_proactive_outreach_person ON proactive_outreach_log(fub_person_id);
CREATE INDEX IF NOT EXISTS idx_proactive_outreach_org ON proactive_outreach_log(organization_id);
CREATE INDEX IF NOT EXISTS idx_proactive_outreach_stage ON proactive_outreach_log(lead_stage);
CREATE INDEX IF NOT EXISTS idx_proactive_outreach_responded ON proactive_outreach_log(lead_responded);
CREATE INDEX IF NOT EXISTS idx_proactive_outreach_triggered_at ON proactive_outreach_log(triggered_at DESC);

COMMENT ON TABLE proactive_outreach_log IS 'Logs all proactive AI outreach attempts with full context and response tracking';
COMMENT ON COLUMN proactive_outreach_log.lead_stage IS 'Lead stage at time of outreach: NEW (0-7 days), DORMANT (30-180 days), WARM (active), COLD (180+ days), RETURNING (re-enabled)';
COMMENT ON COLUMN proactive_outreach_log.strategy_used IS 'Re-engagement strategy: enthusiastic_intro, soft_reconnection, value_first, continuity';
COMMENT ON COLUMN proactive_outreach_log.prior_topics_discussed IS 'Topics extracted from prior messages: budget, timeline, location, etc.';


-- =========================================
-- 2. ADD proactive_outreach_metadata TO ai_conversations
-- =========================================
-- Stores proactive outreach context in the conversation record

ALTER TABLE ai_conversations
ADD COLUMN IF NOT EXISTS proactive_outreach_metadata JSONB;

COMMENT ON COLUMN ai_conversations.proactive_outreach_metadata IS 'Metadata from proactive outreach: {outreach_sent, lead_stage_at_outreach, days_since_last_contact, strategy_used, prior_topics_discussed, questions_already_asked, sent_at}';

-- Example metadata structure:
-- {
--   "outreach_sent": true,
--   "lead_stage_at_outreach": "DORMANT",
--   "days_since_last_contact": 45,
--   "strategy_used": "soft_reconnection",
--   "prior_topics_discussed": ["budget", "timeline"],
--   "questions_already_asked": ["preapproval"],
--   "sent_at": "2026-02-05T20:30:00Z"
-- }


-- =========================================
-- 3. CREATE VIEW FOR ANALYTICS
-- =========================================
-- Easy analytics queries for proactive outreach performance

CREATE OR REPLACE VIEW proactive_outreach_analytics AS
SELECT
    lead_stage,
    strategy_used,
    enable_type,
    COUNT(*) as total_outreach,
    SUM(CASE WHEN sms_sent THEN 1 ELSE 0 END) as sms_sent_count,
    SUM(CASE WHEN email_sent THEN 1 ELSE 0 END) as email_sent_count,
    SUM(CASE WHEN lead_responded THEN 1 ELSE 0 END) as responses,
    ROUND(100.0 * SUM(CASE WHEN lead_responded THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as response_rate_percent,
    AVG(response_time_minutes) as avg_response_time_minutes,
    MIN(triggered_at) as first_outreach,
    MAX(triggered_at) as last_outreach
FROM proactive_outreach_log
GROUP BY lead_stage, strategy_used, enable_type;

COMMENT ON VIEW proactive_outreach_analytics IS 'Analytics view for proactive outreach performance by stage and strategy';


-- =========================================
-- 4. FUNCTION TO UPDATE RESPONSE TRACKING
-- =========================================
-- Automatically mark outreach as responded when lead replies

CREATE OR REPLACE FUNCTION update_proactive_outreach_response()
RETURNS TRIGGER AS $$
DECLARE
    latest_outreach_id UUID;
BEGIN
    -- When a new inbound message is logged
    IF NEW.direction = 'inbound' THEN
        -- Find the most recent proactive outreach log for this person
        SELECT id INTO latest_outreach_id
        FROM proactive_outreach_log
        WHERE
            fub_person_id = NEW.fub_person_id::TEXT
            AND lead_responded = FALSE
            AND sent_at IS NOT NULL
            AND sent_at < NEW.created_at
        ORDER BY sent_at DESC
        LIMIT 1;

        -- Update it if found
        IF latest_outreach_id IS NOT NULL THEN
            UPDATE proactive_outreach_log
            SET
                lead_responded = TRUE,
                responded_at = NEW.created_at,
                response_time_minutes = EXTRACT(EPOCH FROM (NEW.created_at - sent_at)) / 60
            WHERE id = latest_outreach_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger on ai_message_log
DROP TRIGGER IF EXISTS trigger_update_proactive_outreach_response ON ai_message_log;
CREATE TRIGGER trigger_update_proactive_outreach_response
    AFTER INSERT ON ai_message_log
    FOR EACH ROW
    EXECUTE FUNCTION update_proactive_outreach_response();

COMMENT ON FUNCTION update_proactive_outreach_response IS 'Automatically marks proactive outreach as responded when lead sends inbound message';


-- =========================================
-- MIGRATION COMPLETE
-- =========================================
-- Tables created:
-- - proactive_outreach_log (with indexes)
-- Columns added:
-- - ai_conversations.proactive_outreach_metadata
-- Views created:
-- - proactive_outreach_analytics
-- Triggers created:
-- - trigger_update_proactive_outreach_response
