"""
Script to establish FUB browser session locally.
The session will be saved to Supabase and can then be used by Railway.

Run this locally when FUB login needs to be refreshed.
"""

import asyncio
import os
import sys

# Add the Backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

async def setup_fub_session():
    """Establish FUB session and save to Supabase."""

    from app.messaging.playwright_sms_service import PlaywrightSMSServiceSingleton
    from app.database.supabase_client import SupabaseClientSingleton

    print("=" * 60)
    print("FUB Session Setup")
    print("=" * 60)

    supabase = SupabaseClientSingleton.get_instance()

    # Get credentials from environment first
    fub_email = os.getenv("FUB_LOGIN_EMAIL")
    fub_password = os.getenv("FUB_LOGIN_PASSWORD")

    # If not in env, try to get from ai_agent_settings table
    if not fub_email or not fub_password:
        try:
            result = supabase.table("ai_agent_settings").select(
                "fub_login_email, fub_login_password"
            ).limit(1).execute()
            if result.data:
                fub_email = fub_email or result.data[0].get("fub_login_email")
                fub_password = fub_password or result.data[0].get("fub_login_password")
                print("Found FUB credentials in database")
        except Exception as e:
            print(f"Could not query ai_agent_settings: {e}")

    # If still no credentials, prompt
    if not fub_email:
        fub_email = input("Enter FUB login email: ").strip()
    if not fub_password:
        fub_password = input("Enter FUB login password: ").strip()

    print(f"\nUsing email: {fub_email}")

    # Get agent_id - this should match what the webhook handler uses
    # Check the users table for the admin user

    try:
        result = supabase.table("users").select("id, email").eq("role", "admin").limit(1).execute()
        if result.data:
            agent_id = result.data[0]["id"]
            print(f"Using agent_id from admin user: {agent_id}")
        else:
            agent_id = "default_agent"
            print(f"No admin user found, using default agent_id: {agent_id}")
    except Exception as e:
        agent_id = "default_agent"
        print(f"Could not query users table ({e}), using default agent_id: {agent_id}")

    credentials = {
        "type": "email",
        "email": fub_email,
        "password": fub_password,
    }

    print(f"\nEstablishing FUB session for agent_id: {agent_id}")
    print("This will open a browser window. You may need to manually click the verification link if Gmail auto-read fails.")
    print("-" * 60)

    try:
        service = await PlaywrightSMSServiceSingleton.get_instance()
        session = await service.get_or_create_session(agent_id, credentials)

        is_valid = await session.is_valid()

        if is_valid:
            print("\n" + "=" * 60)
            print("SUCCESS! FUB session established and saved to Supabase.")
            print(f"Agent ID: {agent_id}")
            print(f"Base URL: {session._get_base_url()}")
            print("=" * 60)
            print("\nThe session is now available for Railway to use.")
            print("You can close this script - the session will persist.")
        else:
            print("\n" + "=" * 60)
            print("WARNING: Session created but validation failed.")
            print("The browser may still be on a login page.")
            print("=" * 60)

    except Exception as e:
        print(f"\nERROR: {e}")
        print("\nTroubleshooting:")
        print("1. Check FUB credentials are correct")
        print("2. Check Gmail app password is set in .env (GMAIL_APP_PASSWORD)")
        print("3. Check Gmail email is set in .env (GMAIL_EMAIL)")
        print("4. Try logging into FUB manually first to ensure account is active")
        raise

    # Keep running so the browser stays open for debugging if needed
    input("\nPress Enter to close...")

if __name__ == "__main__":
    asyncio.run(setup_fub_session())
