#!/usr/bin/env python3
"""Run the FUB browser login migration directly against the database."""

import os
import sys

# Add Backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2 import sql

# Get database URL from environment
DATABASE_URL = os.getenv("SUPABASE_POSTGRES_URL") or os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: No database URL found.")
    print("Set SUPABASE_POSTGRES_URL or DATABASE_URL in your .env file")
    sys.exit(1)

# First create the ai_agent_settings table if it doesn't exist
CREATE_TABLE_SQL = """
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
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
"""

# Migration SQL statements for FUB login
MIGRATION_SQL = [
    CREATE_TABLE_SQL,
    """
    ALTER TABLE ai_agent_settings
        ADD COLUMN IF NOT EXISTS fub_login_email VARCHAR(255),
        ADD COLUMN IF NOT EXISTS fub_login_password VARCHAR(255),
        ADD COLUMN IF NOT EXISTS fub_login_type VARCHAR(20) DEFAULT 'email';
    """,
    """
    DO $$ BEGIN
        ALTER TABLE ai_agent_settings
            ADD CONSTRAINT ai_settings_login_type_check
            CHECK (fub_login_type IS NULL OR fub_login_type IN ('email', 'google', 'microsoft'));
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """,
    """
    ALTER TABLE ai_agent_settings
        ADD COLUMN IF NOT EXISTS use_assigned_agent_name BOOLEAN DEFAULT false;
    """,
    # Create unique indexes
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_agent_settings_user
        ON ai_agent_settings(user_id) WHERE user_id IS NOT NULL;
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_agent_settings_org
        ON ai_agent_settings(organization_id) WHERE organization_id IS NOT NULL AND user_id IS NULL;
    """,
    # Disable RLS or add permissive policies
    """
    ALTER TABLE ai_agent_settings DISABLE ROW LEVEL SECURITY;
    """,
    """
    GRANT ALL ON ai_agent_settings TO authenticated;
    """,
    """
    GRANT ALL ON ai_agent_settings TO anon;
    """,
    """
    GRANT ALL ON ai_agent_settings TO service_role;
    """
]

def run_migration():
    """Run the migration SQL statements."""
    print("=" * 60)
    print("FUB Browser Login Migration")
    print("=" * 60)
    print()

    try:
        print(f"Connecting to database...")
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor()

        for i, sql_stmt in enumerate(MIGRATION_SQL, 1):
            print(f"Running statement {i}/{len(MIGRATION_SQL)}...")
            try:
                cursor.execute(sql_stmt)
                print(f"  [OK] Statement {i} executed successfully")
            except Exception as e:
                print(f"  [WARN] Statement {i}: {e}")

        # Verify columns exist
        print()
        print("Verifying migration...")
        cursor.execute("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns
            WHERE table_name = 'ai_agent_settings'
            AND column_name IN ('fub_login_email', 'fub_login_password', 'fub_login_type', 'use_assigned_agent_name')
            ORDER BY column_name;
        """)

        columns = cursor.fetchall()
        if columns:
            print("Columns found in ai_agent_settings:")
            for col in columns:
                print(f"  - {col[0]}: {col[1]} (default: {col[2]})")
        else:
            print("WARNING: No columns found. The ai_agent_settings table may not exist.")

        cursor.close()
        conn.close()

        print()
        print("=" * 60)
        print("Migration completed!")
        print("=" * 60)

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_migration()
