"""Verify database setup and test login"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SECRET_KEY")

print(f"Connecting to: {URL}")
print("=" * 60)

supabase = create_client(supabase_url=URL, supabase_key=KEY)

# Check tables exist
print("\n=== CHECKING TABLES ===")
tables = ["organizations", "users", "organization_users", "leads"]
for table in tables:
    try:
        result = supabase.table(table).select("*").limit(1).execute()
        count_result = supabase.table(table).select("*", count="exact").execute()
        print(f"  {table}: EXISTS ({count_result.count} rows)")
        if result.data:
            print(f"    Sample: {list(result.data[0].keys())}")
    except Exception as e:
        print(f"  {table}: ERROR - {e}")

# Check admin user in users table
print("\n=== CHECKING ADMIN USER ===")
try:
    result = supabase.table("users").select("*").eq("email", "adam@saahomes.com").execute()
    if result.data:
        user = result.data[0]
        print(f"  Found user in users table:")
        print(f"    ID: {user.get('id')}")
        print(f"    Email: {user.get('email')}")
        print(f"    Role: {user.get('role')}")
        print(f"    Full Name: {user.get('full_name')}")
    else:
        print("  NO USER FOUND in users table!")
except Exception as e:
    print(f"  Error: {e}")

# Check auth user
print("\n=== CHECKING AUTH USER ===")
try:
    auth_users = supabase.auth.admin.list_users()
    for user in auth_users:
        if user.email == "adam@saahomes.com":
            print(f"  Found in auth.users:")
            print(f"    ID: {user.id}")
            print(f"    Email: {user.email}")
            print(f"    Confirmed: {user.email_confirmed_at is not None}")
            break
    else:
        print("  NOT FOUND in auth.users!")
except Exception as e:
    print(f"  Error: {e}")

# Test login
print("\n=== TESTING LOGIN ===")
try:
    response = supabase.auth.sign_in_with_password({
        "email": "adam@saahomes.com",
        "password": "Vitzer0100!"
    })
    print(f"  Login SUCCESS!")
    print(f"    User ID: {response.user.id}")
    print(f"    Email: {response.user.email}")

    # Now try to fetch user role (what the frontend does)
    print("\n=== TESTING ROLE FETCH (what frontend does) ===")
    user_data = supabase.table("users").select("role").eq("id", response.user.id).single().execute()
    print(f"  Role fetch SUCCESS!")
    print(f"    Role: {user_data.data.get('role')}")

except Exception as e:
    print(f"  Login FAILED: {e}")

print("\n" + "=" * 60)
