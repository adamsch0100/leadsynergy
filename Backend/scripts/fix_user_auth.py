"""
Script to diagnose and fix authentication issues for adam@saahomes.com
"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SECRET_KEY must be set in .env file")
    exit(1)

# Create admin client (using service role key for admin operations)
supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

email = os.getenv("ADMIN_EMAIL", "")
password = os.getenv("ADMIN_PASSWORD", "")

print("=" * 60)
print("DIAGNOSING AUTHENTICATION ISSUE FOR:", email)
print("=" * 60)

# Step 1: Check if user exists in auth.users
print("\n1. Checking Supabase Auth...")
user_found = False
auth_user_id = None

try:
    # Try to get user by email using admin API
    # Note: This requires service role key
    try:
        auth_users_response = supabase.auth.admin.list_users()
        # The response might be a list or have a users attribute
        if hasattr(auth_users_response, 'users'):
            auth_users = auth_users_response.users
        elif isinstance(auth_users_response, list):
            auth_users = auth_users_response
        else:
            auth_users = []
        
        for user in auth_users:
            user_email = getattr(user, 'email', None) or (user.get('email') if isinstance(user, dict) else None)
            if user_email == email:
                user_found = True
                auth_user_id = getattr(user, 'id', None) or (user.get('id') if isinstance(user, dict) else None)
                print(f"   [OK] User found in auth.users")
                print(f"   - User ID: {auth_user_id}")
                print(f"   - Email: {user_email}")
                email_confirmed = getattr(user, 'email_confirmed_at', None) or (user.get('email_confirmed_at') if isinstance(user, dict) else None)
                print(f"   - Email confirmed: {email_confirmed is not None}")
                break
    except Exception as admin_error:
        # If admin API doesn't work, try direct sign-in test
        print(f"   [INFO] Admin API not available, will test sign-in instead")
        pass
    
    if not user_found:
        print(f"   [WARN] User NOT found in auth.users (or couldn't check)")
        print(f"   -> Will test sign-in to verify")
except Exception as e:
    print(f"   [ERROR] Error checking auth: {e}")

# Step 2: Check if user exists in users table
print("\n2. Checking users table...")
try:
    users_result = supabase.table("users").select("*").eq("email", email).execute()
    
    if users_result.data and len(users_result.data) > 0:
        user_data = users_result.data[0]
        print(f"   [OK] User found in users table")
        print(f"   - User ID: {user_data.get('id')}")
        print(f"   - Email: {user_data.get('email')}")
        print(f"   - Role: {user_data.get('role')}")
        print(f"   - Full Name: {user_data.get('full_name')}")
        
        db_user_id = user_data.get('id')
        
        # Check if IDs match
        if auth_user_id and db_user_id != auth_user_id:
            print(f"   [WARN] User IDs don't match!")
            print(f"   - Auth ID: {auth_user_id}")
            print(f"   - DB ID: {db_user_id}")
    else:
        print(f"   [WARN] User NOT found in users table")
        print(f"   -> Need to create user record")
        db_user_id = None
except Exception as e:
    print(f"   [ERROR] Error checking users table: {e}")
    db_user_id = None

# Step 3: Check user_profiles table
print("\n3. Checking user_profiles table...")
try:
    if auth_user_id:
        profile_result = supabase.table("user_profiles").select("*").eq("id", auth_user_id).execute()
        
        if profile_result.data and len(profile_result.data) > 0:
            profile = profile_result.data[0]
            print(f"   [OK] Profile found")
            print(f"   - Onboarding completed: {profile.get('onboarding_completed')}")
            print(f"   - Has FUB API key: {bool(profile.get('fub_api_key'))}")
        else:
            print(f"   [INFO] Profile NOT found (will be auto-created on first login)")
except Exception as e:
    print(f"   [ERROR] Error checking user_profiles: {e}")

# Step 4: Try to sign in
print("\n4. Testing sign-in...")
try:
    # Create a client for auth operations (not admin)
    from supabase import create_client, Client
    auth_client = create_client(SUPABASE_URL, os.getenv("SUPABASE_ANON_KEY") or SUPABASE_SECRET_KEY)
    
    sign_in_result = auth_client.auth.sign_in_with_password({
        "email": email,
        "password": password
    })
    
    if sign_in_result.user:
        print(f"   [OK] Sign-in successful!")
        print(f"   - User ID: {sign_in_result.user.id}")
        print(f"   - Email: {sign_in_result.user.email}")
        auth_user_id = sign_in_result.user.id  # Update with actual ID
        user_found = True
    else:
        print(f"   [ERROR] Sign-in failed: No user returned")
except Exception as e:
    print(f"   [ERROR] Sign-in failed: {e}")
    print(f"   -> This is the main issue!")
    error_msg = str(e)
    if "Invalid login credentials" in error_msg or "Email not confirmed" in error_msg:
        print(f"   -> Possible causes:")
        print(f"      1. Wrong password")
        print(f"      2. Email not confirmed")
        print(f"      3. Account disabled")

# Step 5: Fix recommendations
print("\n" + "=" * 60)
print("RECOMMENDATIONS:")
print("=" * 60)

if not user_found:
    print("\n1. CREATE AUTH USER:")
    print("   - User doesn't exist in Supabase Auth")
    print("   - Options:")
    print("     a) Use Supabase dashboard to create user")
    print("     b) Use signup flow in the app")
    print("     c) Reset password if email exists but password is wrong")
    print("\n   Would you like to reset the password? (requires Supabase dashboard)")

if user_found and db_user_id and auth_user_id and db_user_id != auth_user_id:
    print("\n2. FIX USER ID MISMATCH:")
    print("   - Auth user ID and users table ID don't match")
    print("   - This will cause login failures")
    print("   - Need to update users table to use auth_user_id")
    print(f"\n   Fix command:")
    print(f"   UPDATE users SET id = '{auth_user_id}' WHERE id = '{db_user_id}';")

if user_found and auth_user_id and not db_user_id:
    print("\n3. CREATE USER RECORD:")
    print("   - User exists in auth but not in users table")
    print("   - Need to create matching record in users table")
    print(f"\n   Would you like to create the user record now?")

print("\n" + "=" * 60)
print("Would you like me to attempt automatic fixes? (y/n)")
print("=" * 60)

