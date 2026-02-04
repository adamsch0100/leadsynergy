#!/usr/bin/env python3
"""Quick test of SMS handoff notification only."""

import asyncio
import sys
sys.path.insert(0, '.')

async def main():
    print("=" * 80)
    print("TESTING HANDOFF SMS NOTIFICATION")
    print("=" * 80)
    print()

    from app.messaging.playwright_sms_service import send_sms_with_auto_credentials

    # Settings
    notification_person_id = 3296  # Agent's notification number in FUB
    lead_name = "Adam Schwartz (TEST)"
    handoff_reason = "Lead appears frustrated"
    last_message = "I think you should have my email??"
    fub_link = "https://app.followupboss.com/2/people/view/3314"

    # Build SMS message
    message = f"""HANDOFF ALERT: {lead_name} needs your attention!

Reason: {handoff_reason}
Last message: "{last_message[:80]}"

Respond ASAP: {fub_link}"""

    print(f"Sending SMS to person {notification_person_id}...")
    print()
    print("Message preview:")
    print("-" * 80)
    print(message)
    print("-" * 80)
    print()

    # Send SMS
    result = await send_sms_with_auto_credentials(
        person_id=notification_person_id,
        message=message,
    )

    print()
    print("=" * 80)
    print("RESULT")
    print("=" * 80)
    print()

    if result.get('success'):
        print("SUCCESS! SMS sent to agent notification number.")
        print(f"Check person {notification_person_id} for the SMS.")
    else:
        print("FAILED")
        print(f"Error: {result.get('error', 'Unknown error')}")
    print()

if __name__ == "__main__":
    asyncio.run(main())
