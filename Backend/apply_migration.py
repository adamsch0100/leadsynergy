#!/usr/bin/env python3
"""
Apply the multi-user migration manually using Supabase client
"""
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database.supabase_client import SupabaseClientSingleton

def execute_sql(sql):
    """Execute raw SQL using Supabase RPC"""
    try:
        print(f"Executing: {sql[:50]}...")
        # Note: Supabase doesn't support DDL through RPC, so this will likely fail
        # But let's try anyway
        result = supabase.rpc('exec', {'sql': sql})
        print("Success!")
        return True
    except Exception as e:
        print(f"Failed: {e}")
        return False

def main():
    global supabase
    supabase = SupabaseClientSingleton.get_instance()

    print("=== Applying Multi-User Migration ===")

    # SQL statements to execute
    sql_statements = [
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id UUID PRIMARY KEY,
            version VARCHAR(255) UNIQUE,
            description TEXT,
            applied_at TIMESTAMPTZ DEFAULT NOW()
        );
        """,
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
        """,
        """
        ALTER TABLE leads
            ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE CASCADE;
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_leads_user_id ON leads(user_id);
        """,
        """
        INSERT INTO schema_migrations (id, version, description) VALUES
            (gen_random_uuid(), '20241108_add_multi_user_lead_sources', 'Add user_id and auto_discovered columns to lead_source_settings for multi-user support');
        """
    ]

    success_count = 0
    for i, sql in enumerate(sql_statements, 1):
        print(f"\nStatement {i}/{len(sql_statements)}:")
        if execute_sql(sql.strip()):
            success_count += 1
        else:
            print("Manual execution required for DDL statements")

    print(f"\nCompleted {success_count}/{len(sql_statements)} statements")
    print("\nNOTE: DDL statements (ALTER TABLE, CREATE INDEX) likely need manual execution in Supabase SQL editor")

if __name__ == '__main__':
    main()








