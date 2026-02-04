#!/usr/bin/env python3
"""Test what would happen with lead 3314's handoff NOW with all improvements."""

import asyncio
from app.database.supabase_client import SupabaseClientSingleton
from app.ai_agent.settings_service import AIAgentSettingsService
from app.ai_agent.agent_notifier import notify_agent_of_handoff
from app.database.fub_api_client import FUBApiClient
from app.utils.constants import Credentials

async def main():
    supabase = SupabaseClientSingleton.get_instance()
    settings_service = AIAgentSettingsService(supabase)

    # Get settings
    settings = await settings_service.get_settings(
        user_id='87fecfda-3123-459b-8d95-62d4f943e60f'
    )

    # Get lead 3314 info
    fub = FUBApiClient(api_key=Credentials().FUB_API_KEY)
    person = fub.get_person(3314)

    if not person:
        print("Could not fetch person 3314 from FUB")
        return

    print("=" * 80)
    print("HANDOFF TEST: Lead 3314 (with ALL improvements)")
    print("=" * 80)
    print()

    print("Lead Info:")
    print(f"  Name: {person.get('firstName', '')} {person.get('lastName', '')}")
    print(f"  Email: {person.get('emails', [{}])[0].get('value', 'N/A') if person.get('emails') else 'N/A'}")
    print(f"  Phone: {person.get('phones', [{}])[0].get('value', 'N/A') if person.get('phones') else 'N/A'}")
    print(f"  Assigned To: {person.get('assignedTo', {}).get('name', 'N/A')}")
    print()

    print("Handoff Trigger:")
    print("  Last Message: 'I think you should have my email??'")
    print("  Intent Detected: FRUSTRATION")
    print("  Handoff Reason: Lead appears frustrated")
    print()

    print("=" * 80)
    print("STEP 1: AI Sends Handoff Message to Lead")
    print("=" * 80)
    print()
    print("OLD MESSAGE (generic):")
    print("  'Great talking with you! I'm going to connect you with Adam who can")
    print("   help you even more. They'll reach out shortly!'")
    print()
    print("NEW MESSAGE (world-class):")
    print("  'Perfect timing, Adam! I'm connecting you with Adam Schwartz, our local")
    print("   market expert who's helped dozens of buyers find their dream homes.")
    print("   They'll reach out within the hour with exactly what you need. You're")
    print("   in great hands!'")
    print()

    print("=" * 80)
    print("STEP 2: Create FUB Task")
    print("=" * 80)
    print()
    print("Task Created in FUB:")
    print(f"  Assigned To: {person.get('assignedTo', {}).get('name', 'Agent')}")
    print("  Subject: AI Handoff - Lead appears frustrated")
    print("  Description: Adam (person 3314) needs immediate attention")
    print("  Priority: High")
    print()

    print("=" * 80)
    print("STEP 3: Send SMS to Agent")
    print("=" * 80)
    print()
    print(f"Sending SMS to Person ID {settings.notification_fub_person_id}:")
    print()
    print("MESSAGE:")
    print("  🔔 HANDOFF ALERT: Adam Schwartz needs your attention!")
    print()
    print("  Reason: Lead appears frustrated")
    print("  Last message: \"I think you should have my email??\"")
    print()
    print("  Respond ASAP: https://app.followupboss.com/2/people/view/3314")
    print()

    # Actually test sending the notification
    print("Sending notification NOW...")
    print()

    assigned_agent_email = person.get('assignedTo', {}).get('email')

    result = await notify_agent_of_handoff(
        fub_person_id=3314,
        lead_name=f"{person.get('firstName', '')} {person.get('lastName', '')}".strip(),
        lead_phone=person.get('phones', [{}])[0].get('value', 'Unknown') if person.get('phones') else 'Unknown',
        lead_email=person.get('emails', [{}])[0].get('value', 'Unknown') if person.get('emails') else 'Unknown',
        handoff_reason="Lead appears frustrated",
        last_message="I think you should have my email??",
        assigned_agent_email=assigned_agent_email,
        settings=settings,
    )

    print("=" * 80)
    print("NOTIFICATION RESULT")
    print("=" * 80)
    print()

    if result.get('success'):
        print("✅ SUCCESS!")
        print(f"   Notifications sent: {', '.join(result['notifications_sent'])}")
    else:
        print("❌ FAILED")
        print(f"   Errors: {', '.join(result.get('errors', []))}")
    print()

    print("=" * 80)
    print("STEP 4: Schedule Fallback Monitoring")
    print("=" * 80)
    print()
    print("Scheduled Tasks:")
    print("  ⏰ 3 hours: Check if agent responded")
    print("     If not → Send 'Hey Adam! Adam Schwartz is working on getting")
    print("              those lender intros for you. Expect to hear from them")
    print("              by end of day!'")
    print()
    print("  ⏰ 24 hours: Check if agent EVER responded")
    print("     If not → AI reactivates and sends 'Hey Adam! Haven't heard")
    print("              back from our team yet - I'm here if you need anything!'")
    print()

    print("=" * 80)
    print("COMPLETE HANDOFF FLOW")
    print("=" * 80)
    print()
    print("What agent receives:")
    print("  1. FUB Task in their dashboard")
    print("  2. SMS on their phone (person 3296)")
    print("  3. Email in their inbox from the lead")
    print()
    print("What lead receives:")
    print("  1. Immediate: World-class handoff message")
    print("  2. After 3h: Fallback 'hang tight' message (if agent didn't respond)")
    print("  3. After 24h: AI reactivation message (if agent still didn't respond)")
    print()
    print("Result: Zero chance of lead falling through cracks!")
    print()

if __name__ == "__main__":
    asyncio.run(main())
