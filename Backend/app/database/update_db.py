import os
import uuid
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging
from datetime import datetime
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"supabase_db_setup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("supabase_db_setup")

# Load environment variables
load_dotenv()

# Supabase direct connection URL (from Supabase dashboard)
# Falls back to DATABASE_URL if SUPABASE_DIRECT_URL is not set
SUPABASE_DIRECT_URL = os.getenv("SUPABASE_DIRECT_URL") or os.getenv("DATABASE_URL")

class SupabaseDatabaseSetup:
    def __init__(self, connection_url):
        self.connection_url = connection_url
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Connect to the Supabase PostgreSQL database using direct URL"""
        try:
            logger.info("Connecting to Supabase PostgreSQL database...")
            
            # Connect using the direct URL
            self.conn = psycopg2.connect(self.connection_url)
            
            # Set isolation level to autocommit
            self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            
            # Create a cursor
            self.cursor = self.conn.cursor()
            logger.info("Connected to database successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the database"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def execute_sql(self, sql, description=None):
        """Execute a SQL statement"""
        try:
            if description:
                logger.info(f"Executing: {description}")
            self.cursor.execute(sql)
            return True
        except Exception as e:
            logger.error(f"Error executing SQL: {e}")
            logger.error(f"SQL statement: {sql[:100]}...")
            return False
    
    def create_database_schema(self):
        """Create the complete database schema"""
        if not self.connect():
            return False
        
        try:
            # Create enum types
            logger.info("Creating enum types...")
            self.execute_sql("""
                DO $$ BEGIN
                    CREATE TYPE USER_ROLE AS ENUM ('admin', 'broker', 'agent', 'referral_agent');
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """, "Creating USER_ROLE enum")
            
            self.execute_sql("""
                DO $$ BEGIN
                    CREATE TYPE ASSIGNMENT_TYPE AS ENUM ('jump_ball', 'round_robin', 'specific');
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """, "Creating ASSIGNMENT_TYPE enum")
            
            self.execute_sql("""
                DO $$ BEGIN
                    CREATE TYPE NOTIFICATION_CHANNEL AS ENUM ('email', 'sms', 'both', 'none');
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """, "Creating NOTIFICATION_CHANNEL enum")
            
            self.execute_sql("""
                DO $$ BEGIN
                    CREATE TYPE LEAD_STATUS AS ENUM ('new', 'contacted', 'qualified', 'under_contract', 'closed', 'lost');
                EXCEPTION
                    WHEN duplicate_object THEN null;
                END $$;
            """, "Creating LEAD_STATUS enum")
            
            # Create tables
            logger.info("Creating tables...")
            
            # User profiles table
            self.execute_sql("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id UUID PRIMARY KEY NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    full_name TEXT,
                    phone_number TEXT,
                    role USER_ROLE NOT NULL,
                    fub_api_key TEXT,
                    fub_import_tag TEXT,
                    onboarding_completed BOOLEAN DEFAULT FALSE,
                    notification_preferences NOTIFICATION_CHANNEL DEFAULT 'email',
                    timezone TEXT DEFAULT 'UTC',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE
                );
            """, "Creating user_profiles table")
            
            # Leads table
            self.execute_sql("""
                CREATE TABLE IF NOT EXISTS leads (
                    id UUID PRIMARY KEY NOT NULL,
                    email TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone TEXT,
                    source TEXT,
                    status LEAD_STATUS DEFAULT 'new',
                    fub_person_id TEXT UNIQUE,
                    notes TEXT,
                    fub_tags JSONB,
                    last_webhook_update TIMESTAMPTZ,
                    external_system_data JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """, "Creating leads table")
            
            # Lead source settings table
            self.execute_sql("""
                CREATE TABLE IF NOT EXISTS lead_source_settings (
                    id UUID PRIMARY KEY NOT NULL,
                    source_name TEXT NOT NULL UNIQUE,
                    assignment_strategy ASSIGNMENT_TYPE NOT NULL DEFAULT 'round_robin',
                    referral_fee_percent FLOAT,
                    active BOOLEAN DEFAULT TRUE,
                    metadata JSONB,
                    assignment_rules JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """, "Creating lead_source_settings table")
            
            # Lead assignments table
            self.execute_sql("""
                CREATE TABLE IF NOT EXISTS lead_assignments (
                    id UUID PRIMARY KEY NOT NULL,
                    lead_id UUID NOT NULL,
                    user_id UUID NOT NULL,
                    assignment_type ASSIGNMENT_TYPE NOT NULL,
                    assigned_at TIMESTAMPTZ DEFAULT NOW(),
                    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE,
                    UNIQUE (lead_id, user_id)
                );
            """, "Creating lead_assignments table")
            
            # Webhook events table
            self.execute_sql("""
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
            """, "Creating webhook_events table")
            
            # Lead updates table
            self.execute_sql("""
                CREATE TABLE IF NOT EXISTS lead_updates (
                    id UUID PRIMARY KEY NOT NULL,
                    lead_id UUID NOT NULL,
                    user_id UUID NOT NULL,
                    previous_status LEAD_STATUS,
                    new_status LEAD_STATUS NOT NULL,
                    notes TEXT,
                    webhook_event_id UUID,
                    external_system_id TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE,
                    FOREIGN KEY (webhook_event_id) REFERENCES webhook_events(id) ON DELETE SET NULL
                );
            """, "Creating lead_updates table")
            
            # Lead notes table
            self.execute_sql("""
                CREATE TABLE IF NOT EXISTS lead_notes (
                    id UUID PRIMARY KEY NOT NULL,
                    lead_id UUID NOT NULL,
                    agent_id UUID NOT NULL,
                    note_id TEXT UNIQUE,
                    content TEXT NOT NULL,
                    metadata JSONB,
                    webhook_event_id UUID,
                    external_note_id TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
                    FOREIGN KEY (agent_id) REFERENCES auth.users(id) ON DELETE CASCADE,
                    FOREIGN KEY (webhook_event_id) REFERENCES webhook_events(id) ON DELETE SET NULL
                );
            """, "Creating lead_notes table")
            
            # Activities table
            self.execute_sql("""
                CREATE TABLE IF NOT EXISTS activities (
                    id UUID PRIMARY KEY NOT NULL,
                    lead_id UUID NOT NULL,
                    user_id UUID NOT NULL,
                    type TEXT NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE
                );
            """, "Creating activities table")
            
            # Reminders table
            self.execute_sql("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id UUID PRIMARY KEY NOT NULL,
                    lead_id UUID NOT NULL,
                    user_id UUID NOT NULL,
                    reminder_date TIMESTAMPTZ NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE
                );
            """, "Creating reminders table")
            
            # Stage mappings table
            self.execute_sql("""
                CREATE TABLE IF NOT EXISTS stage_mappings (
                    id UUID PRIMARY KEY NOT NULL,
                    user_id UUID NOT NULL,
                    source_id UUID NOT NULL,
                    fub_stage_id TEXT NOT NULL,
                    fub_stage_name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    platform_stage_name TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE,
                    FOREIGN KEY (source_id) REFERENCES lead_source_settings(id) ON DELETE CASCADE,
                    UNIQUE (user_id, source_id, fub_stage_id)
                );
            """, "Creating stage_mappings table")

            # Lead source aliases table (for mapping duplicate source names)
            self.execute_sql("""
                CREATE TABLE IF NOT EXISTS lead_source_aliases (
                    id UUID PRIMARY KEY NOT NULL DEFAULT gen_random_uuid(),
                    alias_name TEXT NOT NULL,
                    canonical_source_id UUID NOT NULL,
                    user_id UUID NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    FOREIGN KEY (canonical_source_id) REFERENCES lead_source_settings(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE,
                    UNIQUE(alias_name, user_id)
                );
            """, "Creating lead_source_aliases table")

            # Grant permissions on lead_source_aliases table
            self.execute_sql("""
                GRANT ALL ON lead_source_aliases TO authenticated;
            """, "Granting authenticated permissions on lead_source_aliases")

            self.execute_sql("""
                GRANT ALL ON lead_source_aliases TO service_role;
            """, "Granting service_role permissions on lead_source_aliases")

            # Enable RLS and create policy
            self.execute_sql("""
                ALTER TABLE lead_source_aliases ENABLE ROW LEVEL SECURITY;
            """, "Enabling RLS on lead_source_aliases")

            self.execute_sql("""
                DROP POLICY IF EXISTS "Users can manage their own aliases" ON lead_source_aliases;
                CREATE POLICY "Users can manage their own aliases" ON lead_source_aliases
                    FOR ALL
                    USING (auth.uid() = user_id)
                    WITH CHECK (auth.uid() = user_id);
            """, "Creating RLS policy for lead_source_aliases")

            # Allow service role to bypass RLS
            self.execute_sql("""
                DROP POLICY IF EXISTS "Service role has full access" ON lead_source_aliases;
                CREATE POLICY "Service role has full access" ON lead_source_aliases
                    FOR ALL
                    TO service_role
                    USING (true)
                    WITH CHECK (true);
            """, "Creating service_role bypass policy for lead_source_aliases")

            # Notification events log table
            self.execute_sql("""
                CREATE TABLE IF NOT EXISTS notification_events_log (
                    id UUID PRIMARY KEY NOT NULL,
                    user_id UUID NOT NULL,
                    lead_id UUID,
                    trigger_event TEXT NOT NULL,
                    notification_channel NOTIFICATION_CHANNEL NOT NULL,
                    message TEXT,
                    sent_timestamp TIMESTAMPTZ DEFAULT NOW(),
                    delivery_status TEXT,
                    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE,
                    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE SET NULL
                );
            """, "Creating notification_events_log table")
            
            # Commission workflows table
            self.execute_sql("""
                CREATE TABLE IF NOT EXISTS commission_workflows (
                    id UUID PRIMARY KEY NOT NULL,
                    lead_id UUID NOT NULL,
                    transaction_id TEXT UNIQUE,
                    contract_details JSONB,
                    property_address TEXT,
                    contract_date TIMESTAMPTZ,
                    closing_date TIMESTAMPTZ,
                    commission_percentage FLOAT,
                    referral_fee_percentage FLOAT,
                    proof_of_commission_url TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
                );
            """, "Creating commission_workflows table")
            
            # Synchronization logs table
            self.execute_sql("""
                CREATE TABLE IF NOT EXISTS synchronization_logs (
                    id UUID PRIMARY KEY NOT NULL,
                    sync_type TEXT NOT NULL,
                    entities_synced JSONB,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    started_at TIMESTAMPTZ DEFAULT NOW(),
                    completed_at TIMESTAMPTZ,
                    created_by UUID,
                    FOREIGN KEY (created_by) REFERENCES auth.users(id) ON DELETE SET NULL
                );
            """, "Creating synchronization_logs table")
            
            # Tags table
            self.execute_sql("""
                CREATE TABLE IF NOT EXISTS tags (
                    id UUID PRIMARY KEY NOT NULL,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    is_system_tag BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """, "Creating tags table")
            
            # Lead tags table
            self.execute_sql("""
                CREATE TABLE IF NOT EXISTS lead_tags (
                    id UUID PRIMARY KEY NOT NULL,
                    lead_id UUID NOT NULL,
                    tag_id UUID NOT NULL,
                    tagged_at TIMESTAMPTZ DEFAULT NOW(),
                    tagged_by UUID,
                    source TEXT DEFAULT 'fub',
                    FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
                    FOREIGN KEY (tagged_by) REFERENCES auth.users(id) ON DELETE SET NULL,
                    UNIQUE (lead_id, tag_id)
                );
            """, "Creating lead_tags table")
            
            # External system configs table
            self.execute_sql("""
                CREATE TABLE IF NOT EXISTS external_system_configs (
                    id UUID PRIMARY KEY NOT NULL,
                    system_name TEXT NOT NULL UNIQUE,
                    api_url TEXT,
                    api_key TEXT,
                    system_key TEXT,
                    webhook_secret TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    metadata JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
            """, "Creating external_system_configs table")
            
            # Create indexes
            logger.info("Creating indexes...")
            
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source);", "Creating idx_leads_source")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status);", "Creating idx_leads_status")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_leads_fub_person_id ON leads(fub_person_id);", "Creating idx_leads_fub_person_id")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_lead_assignments_lead_id ON lead_assignments(lead_id);", "Creating idx_lead_assignments_lead_id")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_lead_assignments_user_id ON lead_assignments(user_id);", "Creating idx_lead_assignments_user_id")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_lead_updates_lead_id ON lead_updates(lead_id);", "Creating idx_lead_updates_lead_id")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_lead_notes_lead_id ON lead_notes(lead_id);", "Creating idx_lead_notes_lead_id")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_activities_lead_id ON activities(lead_id);", "Creating idx_activities_lead_id")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_activities_user_id ON activities(user_id);", "Creating idx_activities_user_id")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON reminders(user_id);", "Creating idx_reminders_user_id")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_reminders_reminder_date ON reminders(reminder_date);", "Creating idx_reminders_reminder_date")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_stage_mappings_user_source ON stage_mappings(user_id, source_id);", "Creating idx_stage_mappings_user_source")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_commission_workflows_lead_id ON commission_workflows(lead_id);", "Creating idx_commission_workflows_lead_id")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_notification_events_user_id ON notification_events_log(user_id);", "Creating idx_notification_events_user_id")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_webhook_events_event_type ON webhook_events(event_type);", "Creating idx_webhook_events_event_type")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_webhook_events_processed ON webhook_events(processed);", "Creating idx_webhook_events_processed")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_lead_tags_lead_id ON lead_tags(lead_id);", "Creating idx_lead_tags_lead_id")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_lead_tags_tag_id ON lead_tags(tag_id);", "Creating idx_lead_tags_tag_id")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);", "Creating idx_tags_name")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_lead_source_aliases_user ON lead_source_aliases(user_id);", "Creating idx_lead_source_aliases_user")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_lead_source_aliases_canonical ON lead_source_aliases(canonical_source_id);", "Creating idx_lead_source_aliases_canonical")
            self.execute_sql("CREATE INDEX IF NOT EXISTS idx_lead_source_aliases_alias_name ON lead_source_aliases(alias_name);", "Creating idx_lead_source_aliases_alias_name")

            # Create functions
            logger.info("Creating functions...")
            
            self.execute_sql("""
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
            """, "Creating log_webhook_event function")
            
            self.execute_sql("""
                CREATE OR REPLACE FUNCTION mark_webhook_processed(
                    p_event_id UUID,
                    p_status TEXT DEFAULT 'success',
                    p_error_message TEXT DEFAULT NULL
                ) RETURNS VOID AS $$
                BEGIN
                    UPDATE webhook_events
                    SET 
                        processed = TRUE,
                        processing_status = p_status,
                        error_message = p_error_message,
                        processed_at = NOW()
                    WHERE id = p_event_id;
                END;
                $$ LANGUAGE plpgsql;
            """, "Creating mark_webhook_processed function")
            
            # Insert system tags
            logger.info("Inserting system tags...")
            
            self.execute_sql("""
                INSERT INTO tags (id, name, description, is_system_tag)
                VALUES 
                    (gen_random_uuid(), 'ReferralLink', 'Tag for leads imported from referral sources', TRUE),
                    (gen_random_uuid(), 'Processed', 'Tag for leads that have been processed by the system', TRUE),
                    (gen_random_uuid(), 'Assigned', 'Tag for leads that have been assigned to an agent', TRUE),
                    (gen_random_uuid(), 'UnderContract', 'Tag for leads with properties under contract', TRUE),
                    (gen_random_uuid(), 'Closed', 'Tag for leads with closed deals', TRUE)
                ON CONFLICT (name) DO NOTHING;
            """, "Inserting system tags")
            
            logger.info("Database schema created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create database schema: {e}")
            return False
        finally:
            self.disconnect()

def main():
    """Main function to set up the database"""
    logger.info("Starting database setup...")
    
    if not SUPABASE_DIRECT_URL:
        logger.error("SUPABASE_DIRECT_URL environment variable is not set")
        return False
    
    db_setup = SupabaseDatabaseSetup(SUPABASE_DIRECT_URL)
    success = db_setup.create_database_schema()
    
    if success:
        logger.info("Database setup completed successfully")
    else:
        logger.error("Database setup failed")
    
    return success

if __name__ == "__main__":
    main()