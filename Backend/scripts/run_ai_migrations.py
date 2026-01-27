# -*- coding: utf-8 -*-
"""
Run AI Agent Database Migrations.

This script directly executes the AI agent migrations using psycopg2.
Unlike the MigrationManager which uses Supabase client (no DDL support),
this connects directly to PostgreSQL to run schema changes.

Usage:
    cd Backend
    python scripts/run_ai_migrations.py
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in .env file")
    sys.exit(1)

# AI Agent migrations - SQL statements to create required tables
AI_AGENT_MIGRATIONS = [
    # 1. Conversation state tracking
    """
    CREATE TABLE IF NOT EXISTS ai_conversations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        fub_person_id BIGINT NOT NULL,
        user_id UUID,
        organization_id UUID,
        state VARCHAR(50) DEFAULT 'initial',
        lead_score INTEGER DEFAULT 0,
        qualification_data JSONB DEFAULT '{}',
        conversation_history JSONB DEFAULT '[]',
        last_ai_message_at TIMESTAMPTZ,
        last_human_message_at TIMESTAMPTZ,
        handoff_reason VARCHAR(255),
        assigned_agent_id UUID,
        is_active BOOLEAN DEFAULT true,
        re_engagement_count INTEGER DEFAULT 0,
        preferred_channel VARCHAR(20) DEFAULT 'sms',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        last_channel_used VARCHAR(20),
        followup_sequence_id UUID,
        next_followup_at TIMESTAMPTZ,
        channel_reduction VARCHAR(20),
        last_lead_response_at TIMESTAMPTZ,
        CONSTRAINT ai_conversations_state_check
            CHECK (state IN ('initial', 'qualifying', 'objection_handling', 'scheduling', 'nurture', 'handed_off', 'completed', 'engaged')),
        CONSTRAINT ai_conversations_channel_check
            CHECK (preferred_channel IN ('sms', 'email', 'call'))
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_ai_conversations_fub_person ON ai_conversations(fub_person_id);",
    "CREATE INDEX IF NOT EXISTS idx_ai_conversations_user ON ai_conversations(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_ai_conversations_org ON ai_conversations(organization_id);",
    "CREATE INDEX IF NOT EXISTS idx_ai_conversations_state ON ai_conversations(state);",
    "CREATE INDEX IF NOT EXISTS idx_ai_conversations_active ON ai_conversations(is_active) WHERE is_active = true;",
    "CREATE INDEX IF NOT EXISTS idx_ai_conversations_preferred_channel ON ai_conversations(preferred_channel);",
    "CREATE INDEX IF NOT EXISTS idx_ai_conversations_next_followup ON ai_conversations(next_followup_at) WHERE next_followup_at IS NOT NULL;",
    "CREATE INDEX IF NOT EXISTS idx_ai_conversations_last_lead_response ON ai_conversations(last_lead_response_at);",

    # 2. Scheduled messages table
    """
    CREATE TABLE IF NOT EXISTS scheduled_messages (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        conversation_id UUID,
        fub_person_id BIGINT NOT NULL,
        user_id UUID,
        organization_id UUID,
        channel VARCHAR(20) NOT NULL,
        message_template VARCHAR(100),
        message_content TEXT,
        scheduled_for TIMESTAMPTZ NOT NULL,
        sent_at TIMESTAMPTZ,
        status VARCHAR(20) DEFAULT 'pending',
        error_message TEXT,
        retry_count INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        CONSTRAINT scheduled_messages_channel_check
            CHECK (channel IN ('sms', 'email', 'task', 'note')),
        CONSTRAINT scheduled_messages_status_check
            CHECK (status IN ('pending', 'sent', 'cancelled', 'failed', 'skipped'))
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_scheduled_messages_scheduled ON scheduled_messages(scheduled_for) WHERE status = 'pending';",
    "CREATE INDEX IF NOT EXISTS idx_scheduled_messages_conversation ON scheduled_messages(conversation_id);",
    "CREATE INDEX IF NOT EXISTS idx_scheduled_messages_status ON scheduled_messages(status);",

    # 3. AI agent settings
    """
    CREATE TABLE IF NOT EXISTS ai_agent_settings (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID,
        organization_id UUID,
        is_enabled BOOLEAN DEFAULT true,
        response_delay_seconds INTEGER DEFAULT 30,
        working_hours_start TIME DEFAULT '08:00',
        working_hours_end TIME DEFAULT '20:00',
        timezone VARCHAR(50) DEFAULT 'America/New_York',
        auto_handoff_score INTEGER DEFAULT 80,
        max_ai_messages_per_lead INTEGER DEFAULT 15,
        qualification_questions JSONB DEFAULT '[]',
        custom_scripts JSONB DEFAULT '{}',
        personality_tone VARCHAR(50) DEFAULT 'friendly_casual',
        agent_name VARCHAR(100),
        brokerage_name VARCHAR(255),
        re_engagement_enabled BOOLEAN DEFAULT true,
        quiet_hours_before_re_engage INTEGER DEFAULT 24,
        re_engagement_max_attempts INTEGER DEFAULT 3,
        long_term_nurture_after_days INTEGER DEFAULT 7,
        re_engagement_channels JSONB DEFAULT '["sms", "email"]',
        fub_login_email VARCHAR(255),
        fub_login_password VARCHAR(255),
        fub_login_type VARCHAR(20) DEFAULT 'email',
        use_assigned_agent_name BOOLEAN DEFAULT false,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        CONSTRAINT ai_agent_settings_tone_check
            CHECK (personality_tone IN ('friendly_casual', 'professional', 'energetic'))
    );
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_agent_settings_user ON ai_agent_settings(user_id) WHERE user_id IS NOT NULL;",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_agent_settings_org ON ai_agent_settings(organization_id) WHERE organization_id IS NOT NULL AND user_id IS NULL;",

    # 4. Agent availability
    """
    CREATE TABLE IF NOT EXISTS agent_availability (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL,
        day_of_week INTEGER NOT NULL,
        start_time TIME NOT NULL,
        end_time TIME NOT NULL,
        is_available BOOLEAN DEFAULT true,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        CONSTRAINT agent_availability_day_check CHECK (day_of_week >= 0 AND day_of_week <= 6)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_agent_availability_user ON agent_availability(user_id);",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_availability_user_day ON agent_availability(user_id, day_of_week);",

    # 5. Booked appointments
    """
    CREATE TABLE IF NOT EXISTS ai_appointments (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        conversation_id UUID,
        fub_person_id BIGINT,
        fub_appointment_id BIGINT,
        agent_id UUID NOT NULL,
        organization_id UUID,
        google_calendar_event_id VARCHAR(255),
        scheduled_at TIMESTAMPTZ NOT NULL,
        duration_minutes INTEGER DEFAULT 30,
        appointment_type VARCHAR(50) DEFAULT 'consultation',
        status VARCHAR(20) DEFAULT 'scheduled',
        lead_name VARCHAR(255),
        lead_phone VARCHAR(50),
        lead_email VARCHAR(255),
        reminder_sent BOOLEAN DEFAULT false,
        reminder_24h_sent BOOLEAN DEFAULT false,
        notes TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        CONSTRAINT ai_appointments_type_check
            CHECK (appointment_type IN ('showing', 'consultation', 'listing_presentation', 'buyer_consultation', 'phone_call')),
        CONSTRAINT ai_appointments_status_check
            CHECK (status IN ('scheduled', 'confirmed', 'completed', 'cancelled', 'no_show', 'rescheduled'))
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_ai_appointments_agent ON ai_appointments(agent_id);",
    "CREATE INDEX IF NOT EXISTS idx_ai_appointments_scheduled ON ai_appointments(scheduled_at);",
    "CREATE INDEX IF NOT EXISTS idx_ai_appointments_status ON ai_appointments(status);",
    "CREATE INDEX IF NOT EXISTS idx_ai_appointments_fub_person ON ai_appointments(fub_person_id);",

    # 6. SMS Consent tracking
    """
    CREATE TABLE IF NOT EXISTS sms_consent (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        fub_person_id BIGINT NOT NULL,
        phone_number VARCHAR(20) NOT NULL,
        organization_id UUID,
        consent_given BOOLEAN DEFAULT false,
        consent_timestamp TIMESTAMPTZ,
        consent_source VARCHAR(100),
        consent_ip_address VARCHAR(50),
        opted_out BOOLEAN DEFAULT false,
        opted_out_at TIMESTAMPTZ,
        opt_out_reason VARCHAR(255),
        dnc_checked BOOLEAN DEFAULT false,
        dnc_checked_at TIMESTAMPTZ,
        is_on_dnc BOOLEAN DEFAULT false,
        messages_sent_today INTEGER DEFAULT 0,
        last_message_date DATE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        CONSTRAINT sms_consent_source_check
            CHECK (consent_source IS NULL OR consent_source IN ('web_form', 'verbal', 'fub_import', 'text_optin', 'api'))
    );
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_sms_consent_fub_org ON sms_consent(fub_person_id, organization_id);",
    "CREATE INDEX IF NOT EXISTS idx_sms_consent_phone ON sms_consent(phone_number);",
    "CREATE INDEX IF NOT EXISTS idx_sms_consent_opted_out ON sms_consent(opted_out) WHERE opted_out = true;",

    # 7. AI message log
    """
    CREATE TABLE IF NOT EXISTS ai_message_log (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        conversation_id UUID,
        fub_person_id BIGINT NOT NULL,
        direction VARCHAR(10) NOT NULL,
        channel VARCHAR(20) NOT NULL,
        message_content TEXT,
        ai_model VARCHAR(50),
        tokens_used INTEGER,
        response_time_ms INTEGER,
        intent_detected VARCHAR(100),
        sentiment_score DECIMAL(3,2),
        lead_score_delta INTEGER DEFAULT 0,
        extracted_data JSONB DEFAULT '{}',
        fub_message_id BIGINT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        CONSTRAINT ai_message_log_direction_check CHECK (direction IN ('inbound', 'outbound')),
        CONSTRAINT ai_message_log_channel_check CHECK (channel IN ('sms', 'email'))
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_ai_message_log_conversation ON ai_message_log(conversation_id);",
    "CREATE INDEX IF NOT EXISTS idx_ai_message_log_fub_person ON ai_message_log(fub_person_id);",
    "CREATE INDEX IF NOT EXISTS idx_ai_message_log_created ON ai_message_log(created_at);",

    # 8. A/B test results
    """
    CREATE TABLE IF NOT EXISTS ab_test_results (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id UUID,
        user_id UUID,
        conversation_id UUID,
        fub_person_id BIGINT,
        template_category VARCHAR(50) NOT NULL,
        variant_name VARCHAR(50) NOT NULL,
        message_content TEXT,
        sent_at TIMESTAMPTZ DEFAULT NOW(),
        got_response BOOLEAN DEFAULT false,
        response_at TIMESTAMPTZ,
        response_time_seconds INTEGER,
        led_to_appointment BOOLEAN DEFAULT false,
        led_to_optout BOOLEAN DEFAULT false,
        led_to_handoff BOOLEAN DEFAULT false,
        lead_score_before INTEGER,
        lead_score_after INTEGER,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_ab_test_results_org ON ab_test_results(organization_id);",
    "CREATE INDEX IF NOT EXISTS idx_ab_test_results_category ON ab_test_results(template_category);",
    "CREATE INDEX IF NOT EXISTS idx_ab_test_results_variant ON ab_test_results(template_category, variant_name);",
    "CREATE INDEX IF NOT EXISTS idx_ab_test_results_sent ON ab_test_results(sent_at);",

    # 9. Custom field mappings
    """
    CREATE TABLE IF NOT EXISTS ai_custom_field_mappings (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id UUID,
        ai_field VARCHAR(100) NOT NULL,
        fub_field_id VARCHAR(100) NOT NULL,
        fub_field_name VARCHAR(255),
        field_type VARCHAR(50) DEFAULT 'text',
        is_enabled BOOLEAN DEFAULT true,
        sync_direction VARCHAR(20) DEFAULT 'to_fub',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        CONSTRAINT ai_field_mappings_direction_check
            CHECK (sync_direction IN ('to_fub', 'from_fub', 'bidirectional'))
    );
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_field_mappings_org_ai ON ai_custom_field_mappings(organization_id, ai_field);",
    "CREATE INDEX IF NOT EXISTS idx_ai_field_mappings_org ON ai_custom_field_mappings(organization_id);",

    # 10. Scheduled follow-ups
    """
    CREATE TABLE IF NOT EXISTS ai_scheduled_followups (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        fub_person_id BIGINT NOT NULL,
        organization_id UUID NOT NULL,
        scheduled_at TIMESTAMPTZ NOT NULL,
        channel VARCHAR(20) NOT NULL,
        message_type VARCHAR(50) NOT NULL,
        sequence_step INTEGER NOT NULL DEFAULT 0,
        sequence_id UUID NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        executed_at TIMESTAMPTZ,
        cancelled_at TIMESTAMPTZ,
        error_message TEXT,
        CONSTRAINT ai_followups_channel_check
            CHECK (channel IN ('sms', 'email')),
        CONSTRAINT ai_followups_status_check
            CHECK (status IN ('pending', 'sent', 'cancelled', 'failed', 'skipped')),
        CONSTRAINT ai_followups_message_type_check
            CHECK (message_type IN ('gentle_followup', 'value_add', 'channel_switch', 'final_attempt', 'monthly_touchpoint'))
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_ai_followups_scheduled ON ai_scheduled_followups(scheduled_at, status);",
    "CREATE INDEX IF NOT EXISTS idx_ai_followups_person ON ai_scheduled_followups(fub_person_id);",
    "CREATE INDEX IF NOT EXISTS idx_ai_followups_sequence ON ai_scheduled_followups(sequence_id);",
    "CREATE INDEX IF NOT EXISTS idx_ai_followups_org ON ai_scheduled_followups(organization_id);",
    "CREATE INDEX IF NOT EXISTS idx_ai_followups_pending ON ai_scheduled_followups(scheduled_at) WHERE status = 'pending';",

    # 11. Assignment rules
    """
    CREATE TABLE IF NOT EXISTS ai_assignment_rules (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id UUID NOT NULL,
        rule_name VARCHAR(100) NOT NULL,
        rule_type VARCHAR(50) NOT NULL,
        rule_value JSONB NOT NULL,
        is_active BOOLEAN DEFAULT true,
        priority INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        CONSTRAINT ai_rules_type_check
            CHECK (rule_type IN ('stage', 'source', 'date', 'score', 'agent', 'tag'))
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_ai_rules_org ON ai_assignment_rules(organization_id);",
    "CREATE INDEX IF NOT EXISTS idx_ai_rules_active ON ai_assignment_rules(organization_id, is_active) WHERE is_active = true;",
    "CREATE INDEX IF NOT EXISTS idx_ai_rules_type ON ai_assignment_rules(rule_type);",

    # 12. AI campaigns
    """
    CREATE TABLE IF NOT EXISTS ai_campaigns (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        organization_id UUID NOT NULL,
        campaign_name VARCHAR(255) NOT NULL,
        campaign_type VARCHAR(50) NOT NULL,
        status VARCHAR(20) DEFAULT 'scheduled',
        total_leads INTEGER DEFAULT 0,
        leads_processed INTEGER DEFAULT 0,
        messages_sent INTEGER DEFAULT 0,
        leads_responded INTEGER DEFAULT 0,
        leads_converted INTEGER DEFAULT 0,
        daily_limit INTEGER DEFAULT 200,
        lead_filters JSONB DEFAULT '{}',
        target_tiers JSONB DEFAULT '["dormant"]',
        message_template VARCHAR(100),
        custom_message TEXT,
        scheduled_start_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        started_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        cancelled_at TIMESTAMPTZ,
        created_by UUID,
        CONSTRAINT ai_campaigns_type_check
            CHECK (campaign_type IN ('market_update', 'price_drop_alert', 'just_checking_in', 'new_listings', 'custom')),
        CONSTRAINT ai_campaigns_status_check
            CHECK (status IN ('draft', 'scheduled', 'running', 'paused', 'completed', 'cancelled'))
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_ai_campaigns_org ON ai_campaigns(organization_id);",
    "CREATE INDEX IF NOT EXISTS idx_ai_campaigns_status ON ai_campaigns(status);",
    "CREATE INDEX IF NOT EXISTS idx_ai_campaigns_scheduled ON ai_campaigns(scheduled_start_at) WHERE status = 'scheduled';",

    # 13. Campaign leads tracking
    """
    CREATE TABLE IF NOT EXISTS ai_campaign_leads (
        campaign_id UUID NOT NULL,
        fub_person_id BIGINT NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        priority_score INTEGER DEFAULT 0,
        scheduled_batch INTEGER DEFAULT 0,
        sent_at TIMESTAMPTZ,
        responded_at TIMESTAMPTZ,
        converted_at TIMESTAMPTZ,
        error_message TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        PRIMARY KEY (campaign_id, fub_person_id),
        CONSTRAINT ai_campaign_leads_status_check
            CHECK (status IN ('pending', 'sent', 'responded', 'converted', 'skipped', 'failed'))
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_campaign_leads_status ON ai_campaign_leads(campaign_id, status);",
    "CREATE INDEX IF NOT EXISTS idx_campaign_leads_batch ON ai_campaign_leads(campaign_id, scheduled_batch) WHERE status = 'pending';",
    "CREATE INDEX IF NOT EXISTS idx_campaign_leads_person ON ai_campaign_leads(fub_person_id);",

    # 14. Function for timestamp updates
    """
    CREATE OR REPLACE FUNCTION update_ai_conversation_timestamp()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """,

    # 15. Triggers for timestamp updates
    """
    DROP TRIGGER IF EXISTS ai_conversations_updated_at ON ai_conversations;
    CREATE TRIGGER ai_conversations_updated_at
        BEFORE UPDATE ON ai_conversations
        FOR EACH ROW
        EXECUTE FUNCTION update_ai_conversation_timestamp();
    """,
    """
    DROP TRIGGER IF EXISTS ai_agent_settings_updated_at ON ai_agent_settings;
    CREATE TRIGGER ai_agent_settings_updated_at
        BEFORE UPDATE ON ai_agent_settings
        FOR EACH ROW
        EXECUTE FUNCTION update_ai_conversation_timestamp();
    """,
    """
    DROP TRIGGER IF EXISTS ai_appointments_updated_at ON ai_appointments;
    CREATE TRIGGER ai_appointments_updated_at
        BEFORE UPDATE ON ai_appointments
        FOR EACH ROW
        EXECUTE FUNCTION update_ai_conversation_timestamp();
    """,
    """
    DROP TRIGGER IF EXISTS sms_consent_updated_at ON sms_consent;
    CREATE TRIGGER sms_consent_updated_at
        BEFORE UPDATE ON sms_consent
        FOR EACH ROW
        EXECUTE FUNCTION update_ai_conversation_timestamp();
    """,

    # 16. Function for campaign stats auto-update
    """
    CREATE OR REPLACE FUNCTION update_campaign_stats()
    RETURNS TRIGGER AS $$
    BEGIN
        IF NEW.status = 'sent' AND (OLD.status IS NULL OR OLD.status != 'sent') THEN
            UPDATE ai_campaigns
            SET messages_sent = messages_sent + 1,
                leads_processed = leads_processed + 1
            WHERE id = NEW.campaign_id;
        END IF;

        IF NEW.status = 'responded' AND (OLD.status IS NULL OR OLD.status != 'responded') THEN
            UPDATE ai_campaigns
            SET leads_responded = leads_responded + 1
            WHERE id = NEW.campaign_id;
        END IF;

        IF NEW.status = 'converted' AND (OLD.status IS NULL OR OLD.status != 'converted') THEN
            UPDATE ai_campaigns
            SET leads_converted = leads_converted + 1
            WHERE id = NEW.campaign_id;
        END IF;

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """,
    """
    DROP TRIGGER IF EXISTS ai_campaign_leads_stats ON ai_campaign_leads;
    CREATE TRIGGER ai_campaign_leads_stats
        AFTER INSERT OR UPDATE ON ai_campaign_leads
        FOR EACH ROW
        EXECUTE FUNCTION update_campaign_stats();
    """,

    # 17. Add fub_user_id to users table if not exists
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS fub_user_id BIGINT;",
    "CREATE INDEX IF NOT EXISTS idx_users_fub_user_id ON users(fub_user_id) WHERE fub_user_id IS NOT NULL;",
]


def run_migrations():
    """Run all AI agent migrations."""
    print("=" * 60)
    print("AI Agent Database Migrations")
    print("=" * 60)
    print()

    try:
        # Connect to database
        print(f"Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor()
        print("Connected successfully!")
        print()

        # Run each migration
        success_count = 0
        error_count = 0

        for i, sql in enumerate(AI_AGENT_MIGRATIONS, 1):
            # Get first line for display (truncate if too long)
            first_line = sql.strip().split('\n')[0][:60]

            try:
                print(f"[{i}/{len(AI_AGENT_MIGRATIONS)}] {first_line}...")
                cursor.execute(sql)
                success_count += 1
                print(f"    OK")
            except psycopg2.Error as e:
                error_count += 1
                # Check if it's a "already exists" error - that's OK
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print(f"    SKIPPED (already exists)")
                    success_count += 1
                    error_count -= 1
                else:
                    print(f"    ERROR: {e}")

        print()
        print("=" * 60)
        print(f"Migration complete: {success_count} successful, {error_count} errors")
        print("=" * 60)

        # Verify key tables exist
        print()
        print("Verifying key tables...")
        key_tables = [
            'ai_conversations',
            'ai_agent_settings',
            'scheduled_messages',
            'sms_consent',
            'ai_message_log',
        ]

        for table in key_tables:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = %s
                );
            """, (table,))
            exists = cursor.fetchone()[0]
            status = "OK" if exists else "MISSING"
            print(f"  {table}: {status}")

        cursor.close()
        conn.close()

        return error_count == 0

    except psycopg2.Error as e:
        print(f"Database connection failed: {e}")
        return False


if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)
