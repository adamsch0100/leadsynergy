"""Fix LeadSynergy database schema for frontend compatibility"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SECRET_KEY")

print(f"Connecting to: {URL}")
print("-" * 50)

supabase = create_client(supabase_url=URL, supabase_key=KEY)

# The auth user ID we found earlier
ADMIN_USER_ID = "420314bc-0bc8-402f-aac6-12257ca2acf6"
ADMIN_EMAIL = "adam@saahomes.com"
ORG_ID = "a0000000-0000-0000-0000-000000000001"

print("\n=== STEP 1: Check/Create Organizations Table ===")
try:
    # Try to access organizations table
    result = supabase.table("organizations").select("id").limit(1).execute()
    print("  organizations table exists!")
except Exception as e:
    if "does not exist" in str(e):
        print("  organizations table does NOT exist - needs to be created via SQL Editor")
        print("  Please run the FIX_FRONTEND_SCHEMA.sql in Supabase SQL Editor")
    else:
        print(f"  Error: {e}")

print("\n=== STEP 2: Check Users Table Structure ===")
try:
    result = supabase.table("users").select("*").eq("id", ADMIN_USER_ID).execute()
    if result.data:
        print(f"  User found: {result.data[0]}")
    else:
        print("  Admin user not found in users table")
except Exception as e:
    print(f"  Error: {e}")

print("\n=== STEP 3: Try to Create/Update Admin User ===")
try:
    # Try to upsert the admin user
    result = supabase.table("users").upsert({
        "id": ADMIN_USER_ID,
        "email": ADMIN_EMAIL,
        "first_name": "Adam",
        "last_name": "Schwartz",
        "full_name": "Adam Schwartz",
        "role": "admin",
        "is_active": True
    }, on_conflict="id").execute()
    print(f"  Admin user upserted: {result.data}")
except Exception as e:
    print(f"  Error upserting user: {e}")

print("\n=== STEP 4: Try to Create Organization ===")
try:
    result = supabase.table("organizations").upsert({
        "id": ORG_ID,
        "name": "SAA Homes",
        "slug": "saa-homes",
        "subscription_plan": "business",
        "subscription_status": "active",
        "billing_email": ADMIN_EMAIL
    }, on_conflict="id").execute()
    print(f"  Organization upserted: {result.data}")
except Exception as e:
    if "does not exist" in str(e):
        print("  Cannot create - organizations table doesn't exist")
    else:
        print(f"  Error: {e}")

print("\n=== STEP 5: Try to Link User to Organization ===")
try:
    result = supabase.table("organization_users").upsert({
        "organization_id": ORG_ID,
        "user_id": ADMIN_USER_ID,
        "role": "admin",
        "is_primary": True
    }, on_conflict="organization_id,user_id").execute()
    print(f"  Organization user link created: {result.data}")
except Exception as e:
    if "does not exist" in str(e):
        print("  Cannot create - organization_users table doesn't exist")
    else:
        print(f"  Error: {e}")

print("\n=== SUMMARY ===")
print("If tables don't exist, please run the SQL migration in Supabase SQL Editor:")
print("  1. Go to https://supabase.com/dashboard")
print("  2. Select your project (uavuasjvirgbhkszvzyy)")
print("  3. Go to SQL Editor")
print("  4. Paste and run the contents of: Backend/migrations/FIX_FRONTEND_SCHEMA.sql")
print("-" * 50)
