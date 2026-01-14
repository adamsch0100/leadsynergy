"""Check actual database schema"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SECRET_KEY")

print(f"Connecting to: {URL}")
print("-" * 50)

supabase = create_client(supabase_url=URL, supabase_key=KEY)

# Check what's in the users table
print("\n=== USERS TABLE (all columns) ===")
try:
    result = supabase.table("users").select("*").limit(5).execute()
    if result.data:
        print(f"  Columns: {list(result.data[0].keys())}")
        for user in result.data:
            print(f"  User: {user}")
    else:
        print("  No users found!")
except Exception as e:
    print(f"  Error: {e}")

# List all tables we can access
print("\n=== CHECKING TABLES ===")
tables_to_check = [
    "users", "organizations", "organization_users", "leads",
    "team_members", "activities", "subscriptions", "fub_api_keys",
    "athletes", "events", "sports"  # possible other project tables
]

for table in tables_to_check:
    try:
        result = supabase.table(table).select("*").limit(1).execute()
        count = len(result.data) if result.data else 0
        if result.data:
            cols = list(result.data[0].keys())
            print(f"  {table}: EXISTS - columns: {cols[:5]}...")
        else:
            print(f"  {table}: EXISTS (empty)")
    except Exception as e:
        if "does not exist" in str(e):
            print(f"  {table}: NOT FOUND")
        else:
            print(f"  {table}: ERROR - {e}")
