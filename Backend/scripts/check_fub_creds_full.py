# -*- coding: utf-8 -*-
"""
Check FUB credentials in database - full check
"""

import os
import sys
import asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database.supabase_client import SupabaseClientSingleton

async def main():
    print("Checking FUB credentials in database (full check)...")

    supabase = SupabaseClientSingleton.get_instance()

    # Check ai_agent_settings table for FUB login - check if password exists
    print("\n1. Checking ai_agent_settings table for FUB credentials:")
    try:
        result = supabase.table('ai_agent_settings').select('*').execute()

        if result.data:
            for row in result.data:
                print(f"\n   Record ID: {row.get('id')}")
                print(f"   User ID: {row.get('user_id')}")
                print(f"   FUB Login Email: {row.get('fub_login_email')}")
                print(f"   FUB Login Type: {row.get('fub_login_type')}")
                print(f"   FUB Password Set: {'Yes' if row.get('fub_login_password') else 'NO - MISSING!'}")
                print(f"   Agent Name: {row.get('agent_name')}")
                print(f"   Is Enabled: {row.get('is_enabled')}")
        else:
            print("   No records found")
    except Exception as e:
        print(f"   Error: {e}")

    # Now try loading credentials with user_id
    print("\n2. Testing get_fub_browser_credentials with user_id:")
    try:
        from app.ai_agent.settings_service import get_fub_browser_credentials

        user_id = "87fecfda-3123-459b-8d95-62d4f943e60f"
        credentials = await get_fub_browser_credentials(
            supabase_client=supabase,
            user_id=user_id
        )

        if credentials:
            print(f"   [PASS] Credentials found!")
            print(f"   Email: {credentials.get('email')}")
            print(f"   Type: {credentials.get('type')}")
            print(f"   Password: {'*****' if credentials.get('password') else 'NOT SET'}")
            print(f"   Agent ID: {credentials.get('agent_id')}")
        else:
            print("   [FAIL] No credentials returned")

    except Exception as e:
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
