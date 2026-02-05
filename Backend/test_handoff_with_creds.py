#!/usr/bin/env python3
"""Test handoff SMS notification with real production credentials."""

import asyncio
import sys
sys.path.insert(0, '.')

async def main():
    print("=" * 80)
    print("TESTING HANDOFF SMS WITH PRODUCTION CREDENTIALS")
    print("=" * 80)
    print()

    from app.database.supabase_client import SupabaseClientSingleton
    from app.ai_agent.settings_service import AIAgentSettingsService
    from app.ai_agent.agent_notifier import send_sms_to_agent

    # Get production settings
    supabase = SupabaseClientSingleton.get_instance()
    settings_service = AIAgentSettingsService(supabase)
    settings = await settings_service.get_settings(
        user_id='87fecfda-3123-459b-8d95-62d4f943e60f'
    )

    print("Settings loaded:")
    print(f"  Notification Person ID: {settings.notification_fub_person_id}")
    print(f"  SMS Notifications: {'ENABLED' if settings.notify_agent_on_handoff_sms else 'DISABLED'}")
    print()

    if not settings.notify_agent_on_handoff_sms:
        print("ERROR: SMS notifications are disabled in settings")
        return

    if not settings.notification_fub_person_id:
        print("ERROR: No notification_fub_person_id configured")
        return

    # Test message details
    lead_name = "Adam Schwartz (TEST)"
    lead_phone = "(916) 555-1234"
    handoff_reason = "Lead appears frustrated"
    last_message = "I think you should have my email??"
    fub_link = "https://app.followupboss.com/2/people/view/3314"

    print("Sending SMS notification...")
    print()

    # Send the SMS
    result = await send_sms_to_agent(
        notification_person_id=settings.notification_fub_person_id,
        lead_name=lead_name,
        lead_phone=lead_phone,
        handoff_reason=handoff_reason,
        last_message=last_message,
        fub_link=fub_link,
        template=settings.handoff_notification_template,
    )

    print()
    print("=" * 80)
    print("RESULT")
    print("=" * 80)
    print()

    if result:
        print("SUCCESS! Handoff SMS notification sent.")
        print()
        print(f"Check FUB person {settings.notification_fub_person_id} for the SMS message.")
        print("The agent should receive the handoff alert on their phone.")
    else:
        print("FAILED! SMS notification was not sent.")
        print("Check the logs above for error details.")
    print()

if __name__ == "__main__":
    asyncio.run(main())
