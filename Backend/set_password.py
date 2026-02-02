"""Set admin user password in Supabase Auth"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

URL = os.getenv("SUPABASE_URL")
KEY = os.getenv("SUPABASE_SECRET_KEY")  # Service role key needed for admin operations

print(f"Connecting to: {URL}")
print("-" * 50)

supabase = create_client(supabase_url=URL, supabase_key=KEY)

ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "")
NEW_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

print(f"\nUpdating password for user ID: {ADMIN_USER_ID}")

try:
    # Update the user's password using admin API
    response = supabase.auth.admin.update_user_by_id(
        ADMIN_USER_ID,
        {"password": NEW_PASSWORD}
    )
    print(f"Password updated successfully!")
    print(f"User email: {response.user.email}")
    print(f"\nYou can now login with:")
    print(f"  Email: {response.user.email}")
    print(f"  Password: {NEW_PASSWORD}")
except Exception as e:
    print(f"Error updating password: {e}")
