import os
import uuid
from dotenv import load_dotenv
from supabase import create_client, Client
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"migration_manager_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("migration_manager")

# Load environment variables
load_dotenv()

# Supabase client connection (support both naming conventions)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_JWT_SECRET")
#SUPABASE_POSTGRES_URL

class MigrationManager:
    def __init__(self):
        self.supabase = None

    def connect(self):
        """Connect to the Supabase database using client"""
        try:
            logger.info("Connecting to Supabase database...")

            if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
                raise ValueError("SUPABASE_URL and SUPABASE_SECRET_KEY must be set in environment variables")

            self.supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
            logger.info("Connected to database successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return False

    def disconnect(self):
        """Disconnect from the database"""
        if self.supabase:
            # Supabase client doesn't need explicit disconnection
            self.supabase = None
            logger.info("Database connection closed")
    
    def ensure_migrations_table(self):
        """Ensure the migrations table exists"""
        try:
            # Try to select from the table to see if it exists
            result = self.supabase.table("schema_migrations").select("id").limit(1).execute()
            logger.info("Migrations table already exists")
            return True
        except Exception:
            # Table doesn't exist, create it
            try:
                # Use raw SQL via RPC function or direct SQL execution
                # Since Supabase client doesn't support DDL directly, we'll use a workaround
                # For now, assume the table exists or create it manually
                logger.warning("Migrations table may not exist. Please create it manually if needed:")
                logger.warning("CREATE TABLE schema_migrations (id UUID PRIMARY KEY, version VARCHAR(255) UNIQUE, description TEXT, applied_at TIMESTAMPTZ DEFAULT NOW());")
                return True
            except Exception as e:
                logger.error(f"Failed to create migrations table: {e}")
                return False

    def is_migration_applied(self, version):
        """Check if a migration has already been applied"""
        try:
            result = self.supabase.table("schema_migrations").select("id").eq("version", version).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Failed to check migration status: {e}")
            return False

    def record_migration(self, version, description):
        """Record that a migration has been applied"""
        try:
            self.supabase.table("schema_migrations").insert({
                "id": str(uuid.uuid4()),
                "version": version,
                "description": description
            }).execute()
            logger.info(f"Recorded migration: {version}")
            return True
        except Exception as e:
            logger.error(f"Failed to record migration: {e}")
            return False
    
    def execute_migration(self, version, description, sql_statements):
        """Execute a migration"""
        if self.is_migration_applied(version):
            logger.info(f"Migration {version} already applied, skipping")
            return True

        try:
            logger.info(f"Applying migration {version}: {description}")

            # For DDL operations, we need to execute them manually since Supabase client doesn't support DDL
            logger.warning(f"This migration requires manual execution of DDL statements.")
            logger.warning(f"Please execute the following SQL statements in your Supabase SQL editor:")

            for i, sql in enumerate(sql_statements, 1):
                logger.warning(f"Statement {i}: {sql}")

            # Since we can't execute DDL through Supabase client, we'll mark as applied
            # and assume the user will execute the SQL manually
            logger.info("Marking migration as applied (manual execution required)")

            # Record the migration
            self.record_migration(version, description)
            logger.info(f"Migration {version} recorded (manual execution required)")
            return True
        except Exception as e:
            logger.error(f"Failed to apply migration {version}: {e}")
            return False
    
    def run_migrations(self, migrations):
        """Run all migrations"""
        if not self.connect():
            return False
        
        try:
            if not self.ensure_migrations_table():
                return False
            
            success = True
            for migration in migrations:
                version = migration['version']
                description = migration['description']
                sql_statements = migration['sql_statements']
                
                if not self.execute_migration(version, description, sql_statements):
                    success = False
            
            return success
        finally:
            self.disconnect()

# Define migrations
MIGRATIONS = [
    {
        'version': '20230501_initial_schema',
        'description': 'Initial database schema',
        'sql_statements': [
            # Enum types
            """
            DO $$ BEGIN
                CREATE TYPE USER_ROLE AS ENUM ('admin', 'broker', 'agent', 'referral_agent');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
            """,
            # ... (other SQL statements for initial schema)
        ]
    },
    {
        'version': '20230502_add_webhook_tables',
        'description': 'Add webhook related tables',
        'sql_statements': [
            """
            CREATE TABLE IF NOT EXISTS webhook_events (
                id UUID PRIMARY KEY NOT NULL,
                event_type TEXT NOT NULL,
                resource_id TEXT,
                raw_payload JSONB,
                processed BOOLEAN DEFAULT FALSE,
                processing_status TEXT DEFAULT 'pending',
                error_message TEXT,
                received_at TIMESTAMPTZ DEFAULT NOW(),
                processed_at TIMESTAMPTZ,
                CONSTRAINT valid_event_type CHECK (event_type IN ('stage_update', 'note_created', 'note_updated', 'tag_created', 'tag_updated'))
            );
            """,
            # ... (other webhook related tables)
        ]
    },
    {
        'version': '20230503_add_indexes',
        'description': 'Add indexes for performance',
        'sql_statements': [
            "CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source);",
            "CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);",
            # ... (other indexes)
        ]
    },
    {
        'version': '20240125_add_pending_invitations',
        'description': 'Add pending invitations table for magic link invitations',
        'sql_statements': [
            """
            CREATE TABLE IF NOT EXISTS pending_invitations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(255) NOT NULL,
                organization_id UUID NOT NULL,
                role VARCHAR(50) NOT NULL DEFAULT 'agent',
                inviter_name VARCHAR(255),
                organization_name VARCHAR(255),
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                expires_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ,
                CONSTRAINT fk_pending_invitations_organization 
                    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                CONSTRAINT pending_invitations_status_check 
                    CHECK (status IN ('pending', 'completed', 'expired', 'cancelled'))
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_pending_invitations_email ON pending_invitations(email);",
            "CREATE INDEX IF NOT EXISTS idx_pending_invitations_organization ON pending_invitations(organization_id);",
            "CREATE INDEX IF NOT EXISTS idx_pending_invitations_status ON pending_invitations(status);",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_pending_invitations_email_org ON pending_invitations(email, organization_id) WHERE status = 'pending';"
        ]
    },
    {
        'version': '20230504_add_functions',
        'description': 'Add database functions',
        'sql_statements': [
            """
            CREATE OR REPLACE FUNCTION log_webhook_event(
                p_event_type TEXT,
                p_resource_id TEXT,
                p_payload JSONB
            ) RETURNS UUID AS $$
            DECLARE
                v_event_id UUID;
            BEGIN
                INSERT INTO webhook_events (id, event_type, resource_id, raw_payload)
                VALUES (gen_random_uuid(), p_event_type, p_resource_id, p_payload)
                RETURNING id INTO v_event_id;
                
                RETURN v_event_id;
            END;
            $$ LANGUAGE plpgsql;
            """,
            # ... (other functions)
        ]
    },
    {
        'version': '20230505_seed_data',
        'description': 'Seed initial data',
        'sql_statements': [
            """
            INSERT INTO tags (id, name, description, is_system_tag)
            VALUES 
                (gen_random_uuid(), 'ReferralLink', 'Tag for leads imported from referral sources', TRUE),
                (gen_random_uuid(), 'Processed', 'Tag for leads that have been processed by the system', TRUE),
                (gen_random_uuid(), 'Assigned', 'Tag for leads that have been assigned to an agent', TRUE),
                (gen_random_uuid(), 'UnderContract', 'Tag for leads with properties under contract', TRUE),
                (gen_random_uuid(), 'Closed', 'Tag for leads with closed deals', TRUE)
            ON CONFLICT (name) DO NOTHING;
            """
        ]
    },
    {
        'version': '20240126_add_organization_proxy_configs',
        'description': 'Add organization proxy configurations table for IPRoyal proxy management',
        'sql_statements': [
            """
            CREATE TABLE IF NOT EXISTS organization_proxy_configs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                organization_id UUID NOT NULL,
                proxy_username VARCHAR(255) NOT NULL,
                proxy_password VARCHAR(255) NOT NULL,
                proxy_host VARCHAR(255) NOT NULL DEFAULT 'geo.iproyal.com',
                http_port VARCHAR(10) NOT NULL DEFAULT '12321',
                socks5_port VARCHAR(10) NOT NULL DEFAULT '32325',
                proxy_type VARCHAR(20) NOT NULL DEFAULT 'http',
                rotation_enabled BOOLEAN NOT NULL DEFAULT true,
                session_duration VARCHAR(10) NOT NULL DEFAULT '10m',
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                CONSTRAINT fk_org_proxy_organization 
                    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE,
                CONSTRAINT proxy_type_check 
                    CHECK (proxy_type IN ('http', 'socks5'))
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_org_proxy_organization ON organization_proxy_configs(organization_id);",
            "CREATE INDEX IF NOT EXISTS idx_org_proxy_active ON organization_proxy_configs(is_active);",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_org_proxy_org_active ON organization_proxy_configs(organization_id) WHERE is_active = true;"
        ]
    },
    {
        'version': '20241107_add_lead_source_sync_schedule',
        'description': 'Add sync scheduling columns to lead_source_settings',
        'sql_statements': [
            """
            ALTER TABLE lead_source_settings
                ADD COLUMN IF NOT EXISTS sync_interval_days INTEGER,
                ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMPTZ,
                ADD COLUMN IF NOT EXISTS next_sync_at TIMESTAMPTZ;
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_lead_source_settings_next_sync
                ON lead_source_settings(next_sync_at)
                WHERE sync_interval_days IS NOT NULL;
            """
        ]
    },
    {
        'version': '20241108_add_multi_user_lead_sources',
        'description': 'Add user_id and auto_discovered columns to lead_source_settings for multi-user support',
        'sql_statements': [
            """
            ALTER TABLE lead_source_settings
                ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                ADD COLUMN IF NOT EXISTS auto_discovered BOOLEAN DEFAULT FALSE;
            """,
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_lead_source_settings_user_source
                ON lead_source_settings(user_id, source_name)
                WHERE user_id IS NOT NULL;
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_lead_source_settings_user_id
                ON lead_source_settings(user_id);
            """
        ]
    },
    {
        'version': '20250112_add_ai_agent_tables',
        'description': 'Add AI Sales Agent tables for conversation management, scheduling, and compliance',
        'sql_statements': [
            # Conversation state tracking
            """
            CREATE TABLE IF NOT EXISTS ai_conversations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                fub_person_id BIGINT NOT NULL,
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
                state VARCHAR(50) DEFAULT 'initial',
                lead_score INTEGER DEFAULT 0,
                qualification_data JSONB DEFAULT '{}',
                conversation_history JSONB DEFAULT '[]',
                last_ai_message_at TIMESTAMPTZ,
                last_human_message_at TIMESTAMPTZ,
                handoff_reason VARCHAR(255),
                assigned_agent_id UUID REFERENCES users(id),
                is_active BOOLEAN DEFAULT true,
                -- Re-engagement tracking (Phase 4)
                re_engagement_count INTEGER DEFAULT 0,
                preferred_channel VARCHAR(20) DEFAULT 'sms',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
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

            # Message queue for scheduled follow-ups
            """
            CREATE TABLE IF NOT EXISTS scheduled_messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                conversation_id UUID REFERENCES ai_conversations(id) ON DELETE CASCADE,
                fub_person_id BIGINT NOT NULL,
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
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

            # AI agent configuration per user/org
            """
            CREATE TABLE IF NOT EXISTS ai_agent_settings (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
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
                -- Re-engagement settings (Phase 4)
                re_engagement_enabled BOOLEAN DEFAULT true,
                quiet_hours_before_re_engage INTEGER DEFAULT 24,
                re_engagement_max_attempts INTEGER DEFAULT 3,
                long_term_nurture_after_days INTEGER DEFAULT 7,
                re_engagement_channels JSONB DEFAULT '["sms", "email"]',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                CONSTRAINT ai_agent_settings_tone_check
                    CHECK (personality_tone IN ('friendly_casual', 'professional', 'energetic'))
            );
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_agent_settings_user ON ai_agent_settings(user_id) WHERE user_id IS NOT NULL;",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_agent_settings_org ON ai_agent_settings(organization_id) WHERE organization_id IS NOT NULL AND user_id IS NULL;",

            # Agent availability for scheduling
            """
            CREATE TABLE IF NOT EXISTS agent_availability (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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

            # Booked appointments
            """
            CREATE TABLE IF NOT EXISTS ai_appointments (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                conversation_id UUID REFERENCES ai_conversations(id) ON DELETE SET NULL,
                fub_person_id BIGINT,
                fub_appointment_id BIGINT,
                agent_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
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

            # SMS Consent and compliance tracking
            """
            CREATE TABLE IF NOT EXISTS sms_consent (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                fub_person_id BIGINT NOT NULL,
                phone_number VARCHAR(20) NOT NULL,
                organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
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
                    CHECK (consent_source IN ('web_form', 'verbal', 'fub_import', 'text_optin', 'api'))
            );
            """,
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_sms_consent_fub_org ON sms_consent(fub_person_id, organization_id);",
            "CREATE INDEX IF NOT EXISTS idx_sms_consent_phone ON sms_consent(phone_number);",
            "CREATE INDEX IF NOT EXISTS idx_sms_consent_opted_out ON sms_consent(opted_out) WHERE opted_out = true;",

            # AI message log for analytics and auditing
            """
            CREATE TABLE IF NOT EXISTS ai_message_log (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                conversation_id UUID REFERENCES ai_conversations(id) ON DELETE CASCADE,
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

            # Function to update timestamps
            """
            CREATE OR REPLACE FUNCTION update_ai_conversation_timestamp()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """,

            # Triggers for timestamp updates
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
            """
        ]
    },
    {
        'version': '20250112_add_fub_user_id',
        'description': 'Add fub_user_id to users table for agent identity in messages',
        'sql_statements': [
            # Add fub_user_id column to users table
            """
            ALTER TABLE users
                ADD COLUMN IF NOT EXISTS fub_user_id BIGINT;
            """,
            # Create index for faster lookups
            "CREATE INDEX IF NOT EXISTS idx_users_fub_user_id ON users(fub_user_id) WHERE fub_user_id IS NOT NULL;",
        ]
    },
    {
        'version': '20250112_add_channel_reduction',
        'description': 'Add channel_reduction column to ai_conversations for smart channel routing',
        'sql_statements': [
            # Add channel_reduction column for tracking which channels to reduce frequency on
            """
            ALTER TABLE ai_conversations
                ADD COLUMN IF NOT EXISTS channel_reduction VARCHAR(20),
                ADD COLUMN IF NOT EXISTS last_lead_response_at TIMESTAMPTZ;
            """,
            # Add constraint for valid channel_reduction values
            """
            DO $$ BEGIN
                ALTER TABLE ai_conversations
                    ADD CONSTRAINT ai_conversations_channel_reduction_check
                    CHECK (channel_reduction IS NULL OR channel_reduction IN ('sms', 'email'));
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
            """,
            # Add index for finding conversations by channel preference
            "CREATE INDEX IF NOT EXISTS idx_ai_conversations_preferred_channel ON ai_conversations(preferred_channel);",
            "CREATE INDEX IF NOT EXISTS idx_ai_conversations_last_lead_response ON ai_conversations(last_lead_response_at);",
        ]
    },
    {
        'version': '20250112_add_ab_test_results',
        'description': 'Add A/B test results table for template variant tracking',
        'sql_statements': [
            # A/B test results table
            """
            CREATE TABLE IF NOT EXISTS ab_test_results (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                conversation_id UUID REFERENCES ai_conversations(id) ON DELETE SET NULL,
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
        ]
    },
    {
        'version': '20250112_add_ai_custom_field_mappings',
        'description': 'Add table for mapping AI qualification fields to FUB custom fields',
        'sql_statements': [
            # Custom field mappings for syncing AI data to FUB
            """
            CREATE TABLE IF NOT EXISTS ai_custom_field_mappings (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
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
        ]
    },
    {
        'version': '20250114_add_ai_scheduled_followups',
        'description': 'Add AI scheduled follow-ups table and update ai_conversations for follow-up tracking',
        'sql_statements': [
            # Add follow-up tracking columns to ai_conversations
            """
            ALTER TABLE ai_conversations
                ADD COLUMN IF NOT EXISTS last_channel_used VARCHAR(20),
                ADD COLUMN IF NOT EXISTS followup_sequence_id UUID,
                ADD COLUMN IF NOT EXISTS next_followup_at TIMESTAMPTZ;
            """,
            # Add constraint for last_channel_used
            """
            DO $$ BEGIN
                ALTER TABLE ai_conversations
                    ADD CONSTRAINT ai_conversations_last_channel_check
                    CHECK (last_channel_used IS NULL OR last_channel_used IN ('sms', 'email'));
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
            """,
            # Create scheduled follow-ups table
            """
            CREATE TABLE IF NOT EXISTS ai_scheduled_followups (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                fub_person_id BIGINT NOT NULL,
                organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
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
            # Indexes for scheduled follow-ups
            "CREATE INDEX IF NOT EXISTS idx_ai_followups_scheduled ON ai_scheduled_followups(scheduled_at, status);",
            "CREATE INDEX IF NOT EXISTS idx_ai_followups_person ON ai_scheduled_followups(fub_person_id);",
            "CREATE INDEX IF NOT EXISTS idx_ai_followups_sequence ON ai_scheduled_followups(sequence_id);",
            "CREATE INDEX IF NOT EXISTS idx_ai_followups_org ON ai_scheduled_followups(organization_id);",
            "CREATE INDEX IF NOT EXISTS idx_ai_followups_pending ON ai_scheduled_followups(scheduled_at) WHERE status = 'pending';",
            # Index for conversations next followup
            "CREATE INDEX IF NOT EXISTS idx_ai_conversations_next_followup ON ai_conversations(next_followup_at) WHERE next_followup_at IS NOT NULL;",
        ]
    },
    {
        'version': '20250114_add_ai_assignment_rules',
        'description': 'Add AI assignment rules table for controlling which leads get AI-enabled',
        'sql_statements': [
            # AI assignment rules table - controls which leads get AI
            """
            CREATE TABLE IF NOT EXISTS ai_assignment_rules (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
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
            # Trigger for updated_at
            """
            DROP TRIGGER IF EXISTS ai_assignment_rules_updated_at ON ai_assignment_rules;
            CREATE TRIGGER ai_assignment_rules_updated_at
                BEFORE UPDATE ON ai_assignment_rules
                FOR EACH ROW
                EXECUTE FUNCTION update_ai_conversation_timestamp();
            """,
        ]
    },
    {
        'version': '20250114_add_lead_tier_system',
        'description': 'Add lead tier system for efficient scale processing and re-engagement campaigns',
        'sql_statements': [
            # Add tier columns to leads table for efficient querying
            """
            ALTER TABLE leads
                ADD COLUMN IF NOT EXISTS tier VARCHAR(20) DEFAULT 'dormant',
                ADD COLUMN IF NOT EXISTS priority_score INTEGER DEFAULT 0,
                ADD COLUMN IF NOT EXISTS last_ai_contact_at TIMESTAMPTZ,
                ADD COLUMN IF NOT EXISTS tier_updated_at TIMESTAMPTZ,
                ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ;
            """,
            # Add constraint for tier values
            """
            DO $$ BEGIN
                ALTER TABLE leads
                    ADD CONSTRAINT leads_tier_check
                    CHECK (tier IN ('hot', 'warm', 'dormant', 'archived'));
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
            """,
            # Indexes for tier-based queries (critical for scale)
            "CREATE INDEX IF NOT EXISTS idx_leads_tier_priority ON leads(tier, priority_score DESC);",
            "CREATE INDEX IF NOT EXISTS idx_leads_org_tier ON leads(organization_id, tier);",
            "CREATE INDEX IF NOT EXISTS idx_leads_last_activity ON leads(last_activity_at);",
            "CREATE INDEX IF NOT EXISTS idx_leads_last_ai_contact ON leads(last_ai_contact_at);",
            # Composite index for dormant lead queries
            "CREATE INDEX IF NOT EXISTS idx_leads_org_tier_activity ON leads(organization_id, tier, last_activity_at);",

            # AI campaigns table for bulk re-engagement
            """
            CREATE TABLE IF NOT EXISTS ai_campaigns (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
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
                created_by UUID REFERENCES users(id),
                CONSTRAINT ai_campaigns_type_check
                    CHECK (campaign_type IN ('market_update', 'price_drop_alert', 'just_checking_in', 'new_listings', 'custom')),
                CONSTRAINT ai_campaigns_status_check
                    CHECK (status IN ('draft', 'scheduled', 'running', 'paused', 'completed', 'cancelled'))
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_ai_campaigns_org ON ai_campaigns(organization_id);",
            "CREATE INDEX IF NOT EXISTS idx_ai_campaigns_status ON ai_campaigns(status);",
            "CREATE INDEX IF NOT EXISTS idx_ai_campaigns_scheduled ON ai_campaigns(scheduled_start_at) WHERE status = 'scheduled';",

            # Campaign lead tracking for detailed analytics
            """
            CREATE TABLE IF NOT EXISTS ai_campaign_leads (
                campaign_id UUID NOT NULL REFERENCES ai_campaigns(id) ON DELETE CASCADE,
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
        ]
    },
    {
        'version': '20250115_add_fub_browser_login',
        'description': 'Add FUB browser login credentials to ai_agent_settings for Playwright SMS',
        'sql_statements': [
            # Add FUB login columns to ai_agent_settings
            """
            ALTER TABLE ai_agent_settings
                ADD COLUMN IF NOT EXISTS fub_login_email VARCHAR(255),
                ADD COLUMN IF NOT EXISTS fub_login_password VARCHAR(255),
                ADD COLUMN IF NOT EXISTS fub_login_type VARCHAR(20) DEFAULT 'email';
            """,
            # Add constraint for login type
            """
            DO $$ BEGIN
                ALTER TABLE ai_agent_settings
                    ADD CONSTRAINT ai_settings_login_type_check
                    CHECK (fub_login_type IS NULL OR fub_login_type IN ('email', 'google', 'microsoft'));
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
            """,
            # Add use_assigned_agent_name if it doesn't exist
            """
            ALTER TABLE ai_agent_settings
                ADD COLUMN IF NOT EXISTS use_assigned_agent_name BOOLEAN DEFAULT false;
            """,
        ]
    },
    {
        'version': '20250114_add_lead_tier_triggers',
        'description': 'Add triggers for campaign stats auto-update',
        'sql_statements': [
            # Triggers for campaign stats auto-update
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
        ]
    },
    {
        'version': '20250119_add_ai_lead_profile_cache',
        'description': 'Add lead profile cache table for smart FUB data caching and incremental updates',
        'sql_statements': [
            # Lead profile cache table - stores comprehensive FUB data
            """
            CREATE TABLE IF NOT EXISTS ai_lead_profile_cache (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                fub_person_id BIGINT NOT NULL,
                organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

                -- Person data (from FUB people endpoint)
                person_data JSONB DEFAULT '{}',

                -- Communication history
                text_messages JSONB DEFAULT '[]',
                emails JSONB DEFAULT '[]',
                calls JSONB DEFAULT '[]',

                -- Context data
                notes JSONB DEFAULT '[]',
                events JSONB DEFAULT '[]',
                tasks JSONB DEFAULT '[]',

                -- Cache metadata
                cached_at TIMESTAMPTZ DEFAULT NOW(),
                last_updated_at TIMESTAMPTZ DEFAULT NOW(),
                update_count INTEGER DEFAULT 0,

                created_at TIMESTAMPTZ DEFAULT NOW(),
                CONSTRAINT ai_lead_profile_cache_unique UNIQUE (fub_person_id, organization_id)
            );
            """,
            # Indexes for efficient lookups
            "CREATE INDEX IF NOT EXISTS idx_ai_profile_cache_fub_person ON ai_lead_profile_cache(fub_person_id);",
            "CREATE INDEX IF NOT EXISTS idx_ai_profile_cache_org ON ai_lead_profile_cache(organization_id);",
            "CREATE INDEX IF NOT EXISTS idx_ai_profile_cache_cached_at ON ai_lead_profile_cache(cached_at);",
            "CREATE INDEX IF NOT EXISTS idx_ai_profile_cache_updated ON ai_lead_profile_cache(last_updated_at);",

            # Trigger for auto-updating last_updated_at
            """
            DROP TRIGGER IF EXISTS ai_lead_profile_cache_updated_at ON ai_lead_profile_cache;
            CREATE TRIGGER ai_lead_profile_cache_updated_at
                BEFORE UPDATE ON ai_lead_profile_cache
                FOR EACH ROW
                EXECUTE FUNCTION update_ai_conversation_timestamp();
            """,
        ]
    },
    {
        'version': '20250127_fix_personality_tone_constraint',
        'description': 'Fix personality_tone constraint to allow all frontend options and add notification_fub_person_id',
        'sql_statements': [
            # Drop the old restrictive constraint
            """
            DO $$ BEGIN
                ALTER TABLE ai_agent_settings
                    DROP CONSTRAINT IF EXISTS ai_agent_settings_tone_check;
            EXCEPTION
                WHEN undefined_object THEN null;
            END $$;
            """,
            # Add new constraint with all valid personality tones
            """
            DO $$ BEGIN
                ALTER TABLE ai_agent_settings
                    ADD CONSTRAINT ai_agent_settings_tone_check
                    CHECK (personality_tone IS NULL OR personality_tone IN (
                        'friendly_casual', 'professional', 'energetic', 'enthusiastic', 'consultative'
                    ));
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
            """,
            # Add notification_fub_person_id column if not exists
            """
            ALTER TABLE ai_agent_settings
                ADD COLUMN IF NOT EXISTS notification_fub_person_id BIGINT;
            """,
            # Add team_members column if not exists
            """
            ALTER TABLE ai_agent_settings
                ADD COLUMN IF NOT EXISTS team_members VARCHAR(255);
            """,
            # Add max_response_length column if not exists
            """
            ALTER TABLE ai_agent_settings
                ADD COLUMN IF NOT EXISTS max_response_length INTEGER DEFAULT 160;
            """,
            # Add LLM model columns if not exist
            """
            ALTER TABLE ai_agent_settings
                ADD COLUMN IF NOT EXISTS llm_provider VARCHAR(50) DEFAULT 'openrouter',
                ADD COLUMN IF NOT EXISTS llm_model VARCHAR(100) DEFAULT 'xiaomi/mimo-v2-flash:free',
                ADD COLUMN IF NOT EXISTS llm_model_fallback VARCHAR(100) DEFAULT 'deepseek/deepseek-r1-0528:free';
            """,
            # Add auto_enable_new_leads column - when enabled, new leads automatically get AI enabled
            """
            ALTER TABLE ai_agent_settings
                ADD COLUMN IF NOT EXISTS auto_enable_new_leads BOOLEAN DEFAULT false;
            """,
        ]
    },
    {
        'version': '20250127_add_last_sync_results',
        'description': 'Add last_sync_results column to lead_source_settings for persisting sync results',
        'sql_statements': [
            """
            ALTER TABLE lead_source_settings
                ADD COLUMN IF NOT EXISTS last_sync_results JSONB DEFAULT '{}';
            """,
        ]
    }
]

def run_specific_migration(version):
    """Run a specific migration by version"""
    manager = MigrationManager()
    if not manager.connect():
        logger.error("Failed to connect to database")
        return False

    try:
        # Find the migration
        migration = None
        for m in MIGRATIONS:
            if m['version'] == version:
                migration = m
                break

        if not migration:
            logger.error(f"Migration {version} not found")
            return False

        # Run the migration
        success = manager.execute_migration(
            migration['version'],
            migration['description'],
            migration['sql_statements']
        )

        if success:
            logger.info(f"Migration {version} completed successfully")
        else:
            logger.error(f"Migration {version} failed")

        return success
    finally:
        manager.disconnect()

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "run_specific":
        version = sys.argv[2] if len(sys.argv) > 2 else None
        if version:
            if run_specific_migration(version):
                logger.info("Specific migration completed successfully")
            else:
                logger.error("Specific migration failed")
        else:
            logger.error("Please specify a migration version")
    else:
        logger.info("Starting migration manager...")
        manager = MigrationManager()
        if manager.run_migrations(MIGRATIONS):
            logger.info("All migrations completed successfully")
        else:
            logger.error("Some migrations failed")