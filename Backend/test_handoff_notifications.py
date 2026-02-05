#!/usr/bin/env python3
"""Test the handoff notification system with real SMS + Email."""

import asyncio
import sys
sys.path.insert(0, '.')

from app.ai_agent.settings_service import AIAgentSettingsService
from app.ai_agent.agent_notifier import notify_agent_of_handoff
from app.database.supabase_client import SupabaseClientSingleton

async def main():
    print("=" * 80)
    print("TESTING HANDOFF NOTIFICATION SYSTEM")
    print("=" * 80)
    print()

    supabase = SupabaseClientSingleton.get_instance()
    settings_service = AIAgentSettingsService(supabase)

    # Get settings
    settings = await settings_service.get_settings(
        user_id='87fecfda-3123-459b-8d95-62d4f943e60f'
    )

    print("Settings:")
    print(f"  Agent Name: {settings.agent_name}")
    print(f"  Notification Person ID: {settings.notification_fub_person_id}")
    print(f"  SMS Enabled: {settings.notify_agent_on_handoff_sms}")
    print(f"  Email Enabled: {settings.notify_agent_on_handoff_email}")
    print()

    if not settings.notification_fub_person_id:
        print("ERROR: No notification_fub_person_id configured!")
        print("Set this in AI Agent settings to receive SMS alerts.")
        return

    print("Sending TEST handoff notification...")
    print()

    # Send test notification
    result = await notify_agent_of_handoff(
        fub_person_id=3314,  # Test lead
        lead_name="Adam Schwartz (TEST)",
        lead_phone="(916) 555-1234",
        lead_email="test@example.com",
        handoff_reason="🧪 TEST: Lead appears frustrated",
        last_message="I think you should have my email??",
        assigned_agent_email="adam@saahomes.com",  # Your email
        settings=settings,
    )

    print("=" * 80)
    print("RESULT")
    print("=" * 80)
    print()

    if result.get('success'):
        print("✅ SUCCESS!")
        print()
        print("Notifications sent:")
        for notification in result['notifications_sent']:
            print(f"  ✅ {notification}")
        print()

        if 'SMS' in result['notifications_sent']:
            print(f"Check your phone for SMS at person {settings.notification_fub_person_id}")

        if 'Email' in result['notifications_sent']:
            print("Check your inbox (adam@saahomes.com) for email from lead")

    else:
        print("❌ FAILED")
        print()
        print("Errors:")
        for error in result.get('errors', []):
            print(f"  ❌ {error}")

    print()
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
