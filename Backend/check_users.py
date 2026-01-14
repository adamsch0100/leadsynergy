"""Quick script to check Supabase users and auth status"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SECRET_KEY")

print(f"Connecting to: {URL}")
print("-" * 50)

supabase = create_client(supabase_url=URL, supabase_key=KEY)

# Check users table
print("\n=== USERS TABLE ===")
try:
    result = supabase.table("users").select("id, email, full_name, role, created_at").execute()
    if result.data:
        for user in result.data:
            print(f"  Email: {user.get('email')}")
            print(f"  Name: {user.get('full_name')}")
            print(f"  Role: {user.get('role')}")
            print(f"  ID: {user.get('id')}")
            print("-" * 30)
    else:
        print("  No users found in users table!")
except Exception as e:
    print(f"  Error: {e}")

# Check organizations
print("\n=== ORGANIZATIONS TABLE ===")
try:
    result = supabase.table("organizations").select("id, name, subscription_status, subscription_plan").execute()
    if result.data:
        for org in result.data:
            print(f"  Name: {org.get('name')}")
            print(f"  Plan: {org.get('subscription_plan')}")
            print(f"  Status: {org.get('subscription_status')}")
            print("-" * 30)
    else:
        print("  No organizations found!")
except Exception as e:
    print(f"  Error: {e}")

# Check auth users (requires service role key)
print("\n=== AUTH USERS (Supabase Auth) ===")
try:
    auth_users = supabase.auth.admin.list_users()
    if auth_users:
        for user in auth_users:
            print(f"  Email: {user.email}")
            print(f"  ID: {user.id}")
            print(f"  Confirmed: {user.email_confirmed_at is not None}")
            print("-" * 30)
    else:
        print("  No auth users found!")
except Exception as e:
    print(f"  Error listing auth users: {e}")

print("\n=== DONE ===")
