"""
Script to reset password for adam@saahomes.com
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

email = "adam@saahomes.com"
new_password = "Vitzer0100!"  # Reset to this password

print("=" * 60)
print("RESETTING PASSWORD FOR:", email)
print("=" * 60)

try:
    # Get user by email
    auth_users_response = supabase.auth.admin.list_users()
    
    # Handle different response formats
    if hasattr(auth_users_response, 'users'):
        auth_users = auth_users_response.users
    elif isinstance(auth_users_response, list):
        auth_users = auth_users_response
    else:
        auth_users = []
    
    user_found = False
    user_id = None
    
    for user in auth_users:
        user_email = getattr(user, 'email', None) or (user.get('email') if isinstance(user, dict) else None)
        if user_email == email:
            user_found = True
            user_id = getattr(user, 'id', None) or (user.get('id') if isinstance(user, dict) else None)
            break
    
    if not user_found:
        print(f"\n[ERROR] User {email} not found in Supabase Auth")
        print("Cannot reset password for non-existent user")
        exit(1)
    
    print(f"\n[OK] User found: {user_id}")
    print(f"\nResetting password...")
    
    # Reset password using admin API
    result = supabase.auth.admin.update_user_by_id(
        user_id,
        {"password": new_password}
    )
    
    print(f"[OK] Password reset successful!")
    print(f"\nNew password: {new_password}")
    print(f"\nYou can now log in with:")
    print(f"  Email: {email}")
    print(f"  Password: {new_password}")
    
    # Test the new password
    print(f"\nTesting new password...")
    from supabase import create_client
    test_client = create_client(SUPABASE_URL, os.getenv("SUPABASE_ANON_KEY") or SUPABASE_SECRET_KEY)
    test_result = test_client.auth.sign_in_with_password({
        "email": email,
        "password": new_password
    })
    
    if test_result.user:
        print(f"[OK] Password test successful! You can now log in.")
    else:
        print(f"[WARN] Password reset but test sign-in failed")
        
except Exception as e:
    print(f"\n[ERROR] Failed to reset password: {e}")
    print(f"\nAlternative: Use Supabase Dashboard")
    print(f"1. Go to your Supabase project dashboard")
    print(f"2. Navigate to Authentication > Users")
    print(f"3. Find {email}")
    print(f"4. Click 'Reset Password' or 'Update User'")
    print(f"5. Set new password to: {new_password}")

