"""
Run database migration for proactive outreach system.
"""
import os
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'ignore')

from dotenv import load_dotenv
from app.database.supabase_client import SupabaseClientSingleton

def run_migration():
    """Run the proactive outreach schema migration."""
    load_dotenv()

    # Read the SQL file
    migration_path = os.path.join(
        os.path.dirname(__file__),
        "app/database/migrations/add_proactive_outreach_schema.sql"
    )

    print(f"Reading migration from: {migration_path}")

    with open(migration_path, 'r', encoding='utf-8') as f:
        migration_sql = f.read()

    # Connect to Supabase
    print("Connecting to Supabase...")
    supabase = SupabaseClientSingleton.get_instance()

    # Execute the migration
    print("Running migration...")

    try:
        # Note: Supabase Python client doesn't support raw SQL execution directly
        # We need to use the REST API with RPC or execute via psycopg2

        # Execute as single script (handles multi-line statements correctly)
        print("Executing migration script...")

        # Since Supabase client doesn't support raw SQL, we'll need to use psycopg2
        import psycopg2

        # Get connection string from env
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SECRET_KEY')

        # Note: For direct database access, we'd need DATABASE_URL
        # Let's check if it exists
        database_url = os.getenv('DATABASE_URL')

        if not database_url:
            print("\n❌ DATABASE_URL not found in .env file")
            print("This migration requires direct database access.")
            print("\nPlease either:")
            print("1. Add DATABASE_URL to your .env file, OR")
            print("2. Run this SQL manually in Supabase SQL Editor:")
            print(f"\n   Open: {supabase_url.replace('https://', 'https://app.')}/project/_/sql")
            print(f"\n   Then paste the contents of:")
            print(f"   {migration_path}")
            return False

        # Connect and execute entire script
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()

        # Execute the entire migration script at once
        cursor.execute(migration_sql)

        conn.commit()
        cursor.close()
        conn.close()

        print("\n✅ Migration completed successfully!")
        return True

    except ImportError:
        print("\n❌ psycopg2 not installed")
        print("Please install: pip install psycopg2-binary")
        print("\nOR run the migration manually in Supabase SQL Editor:")
        print(migration_path)
        return False

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print("\nYou can run this migration manually in Supabase SQL Editor:")
        print(migration_path)
        return False

if __name__ == '__main__':
    run_migration()
