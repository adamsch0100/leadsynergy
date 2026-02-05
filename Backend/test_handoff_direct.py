#!/usr/bin/env python3
"""Direct test of SMS sending with explicit credential passing."""

import asyncio
import sys
sys.path.insert(0, '.')

async def main():
    print("Step 1: Import Supabase client...")
    from app.database.supabase_client import SupabaseClientSingleton
    supabase = SupabaseClientSingleton.get_instance()
    print("  OK")

    print()
    print("Step 2: Load AI agent settings...")
    from app.ai_agent.settings_service import AIAgentSettingsService
    settings_service = AIAgentSettingsService(supabase)
    settings = await settings_service.get_settings(
        user_id='87fecfda-3123-459b-8d95-62d4f943e60f'
    )
    print(f"  OK - User ID: {settings.user_id}")
    print(f"  OK - Org ID: {settings.organization_id}")
    print(f"  OK - Notification Person: {settings.notification_fub_person_id}")

    print()
    print("Step 3: Get FUB browser credentials...")
    from app.ai_agent.settings_service import get_fub_browser_credentials
    creds = await get_fub_browser_credentials(
        supabase_client=supabase,
        user_id=settings.user_id,
        organization_id=settings.organization_id,
    )
    print(f"  OK - Email: {'SET' if creds.get('email') else 'NOT SET'}")
    print(f"  OK - Password: {'SET' if creds.get('password') else 'NOT SET'}")

    if not creds.get('email') or not creds.get('password'):
        print()
        print("ERROR: Credentials not available!")
        return

    print()
    print("Step 4: Import Playwright SMS service...")
    from app.messaging.playwright_sms_service import send_sms_with_auto_credentials
    print("  OK")

    print()
    print("Step 5: Send test SMS...")
    message = f"""HANDOFF ALERT: Adam Schwartz (TEST) needs your attention!

Reason: Lead appears frustrated
Last message: "I think you should have my email??"

Respond ASAP: https://app.followupboss.com/2/people/view/3314"""

    result = await send_sms_with_auto_credentials(
        person_id=settings.notification_fub_person_id,
        message=message,
        user_id=settings.user_id,
        organization_id=settings.organization_id,
        supabase_client=supabase,
    )

    print()
    print("=" * 80)
    print("RESULT")
    print("=" * 80)

    if result.get('success'):
        print("SUCCESS! SMS sent.")
        print(f"Check person {settings.notification_fub_person_id} in FUB for the message.")
    else:
        print("FAILED!")
        print(f"Error: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    asyncio.run(main())
