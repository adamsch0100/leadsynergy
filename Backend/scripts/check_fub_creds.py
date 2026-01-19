# -*- coding: utf-8 -*-
"""
Check FUB credentials in database
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database.supabase_client import SupabaseClientSingleton

def main():
    print("Checking FUB credentials in database...")

    supabase = SupabaseClientSingleton.get_instance()

    # Check ai_agent_settings table for FUB login
    print("\n1. Checking ai_agent_settings table:")
    try:
        result = supabase.table('ai_agent_settings').select(
            'id, user_id, fub_login_email, fub_login_type'
        ).execute()

        if result.data:
            for row in result.data:
                print(f"   Found: user_id={row.get('user_id')}, email={row.get('fub_login_email')}, type={row.get('fub_login_type')}")
        else:
            print("   No records found")
    except Exception as e:
        print(f"   Error: {e}")

    # Check users table for FUB credentials
    print("\n2. Checking users table for FUB credentials:")
    try:
        result = supabase.table('users').select(
            'id, email, fub_login_email, fub_login_type, fub_terms_accepted'
        ).not_.is_('fub_login_email', 'null').execute()

        if result.data:
            for row in result.data:
                print(f"   Found: email={row.get('email')}, fub_email={row.get('fub_login_email')}, type={row.get('fub_login_type')}, terms={row.get('fub_terms_accepted')}")
        else:
            print("   No users with FUB credentials found")
    except Exception as e:
        print(f"   Error: {e}")

    # Check if there are any users at all
    print("\n3. Checking for any users:")
    try:
        result = supabase.table('users').select('id, email').limit(5).execute()
        if result.data:
            for row in result.data:
                print(f"   User: {row.get('email')}")
        else:
            print("   No users found")
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    main()
