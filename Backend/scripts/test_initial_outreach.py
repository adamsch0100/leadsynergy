"""
Test AI-powered initial outreach generation.

This script generates a preview of the AI-created SMS + Email for a new lead,
WITHOUT actually sending anything. Use this to review what would be sent.

Usage:
    python scripts/test_initial_outreach.py 3293
    python scripts/test_initial_outreach.py 3293 --send  # Actually send
"""

import asyncio
import os
import sys
import argparse
import logging
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Add Backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_outreach(person_id: int, send: bool = False):
    """Test AI outreach generation for a lead."""
    import requests
    import base64

    from app.ai_agent.initial_outreach_generator import (
        generate_initial_outreach,
        LeadContext,
    )

    print("\n" + "=" * 70)
    print(f"AI INITIAL OUTREACH TEST - Lead #{person_id}")
    print("=" * 70)

    # Get FUB API key
    fub_api_key = os.getenv('FUB_API_KEY')
    if not fub_api_key:
        print("ERROR: FUB_API_KEY not set")
        return

    headers = {
        'Authorization': f'Basic {base64.b64encode(f"{fub_api_key}:".encode()).decode()}',
    }

    # Fetch person data
    print("\n1. Fetching lead data from FUB...")
    resp = requests.get(
        f'https://api.followupboss.com/v1/people/{person_id}',
        headers=headers,
        timeout=30,
    )

    if resp.status_code != 200:
        print(f"   ERROR: Could not fetch person: {resp.status_code}")
        return

    person_data = resp.json()
    first_name = person_data.get('firstName', 'there')
    last_name = person_data.get('lastName', '')
    source = person_data.get('source', '')

    emails = person_data.get('emails', [])
    phones = person_data.get('phones', [])
    email = emails[0].get('value', 'N/A') if emails else 'N/A'
    phone = phones[0].get('value', 'N/A') if phones else 'N/A'

    print(f"   Name: {first_name} {last_name}")
    print(f"   Email: {email}")
    print(f"   Phone: {phone}")
    print(f"   Source: {source}")

    # Fetch events for context
    print("\n2. Fetching events for context...")
    resp = requests.get(
        f'https://api.followupboss.com/v1/events?personId={person_id}&limit=5',
        headers=headers,
        timeout=30,
    )

    events = []
    if resp.status_code == 200:
        events = resp.json().get('events', [])
        print(f"   Found {len(events)} events")
        for event in events:
            desc = event.get('description', 'N/A')[:80]
            print(f"   - {desc}")
    else:
        print("   Could not fetch events")

    # Build lead context
    print("\n3. Building lead context...")
    lead_ctx = LeadContext.from_fub_data(person_data, events)

    print(f"   Location: {lead_ctx.get_location_str()}")
    print(f"   Price Range: {lead_ctx.get_price_str() or 'Not specified'}")
    print(f"   Timeline: {lead_ctx.timeline or 'Not specified'}")
    print(f"   Financing: {lead_ctx.financing_status or 'Not specified'}")
    print(f"   Tags: {lead_ctx.tags}")

    # Generate AI outreach
    print("\n4. Generating AI-powered outreach...")
    print("   (Calling Claude API...)")

    try:
        outreach = await generate_initial_outreach(
            person_data=person_data,
            events=events,
            agent_name="Adam",  # Your agent name
            agent_email="adam@saahomes.com",  # Your email
            agent_phone="(916) 555-1234",  # Your phone
            brokerage_name="Schwartz and Associates",
        )

        print(f"   Model used: {outreach.model_used}")
        print(f"   Tokens: {outreach.tokens_used}")
        print(f"   Context used: {outreach.context_used}")

        # Display SMS
        print("\n" + "=" * 70)
        print("GENERATED SMS MESSAGE")
        print("=" * 70)
        print(f"\n{outreach.sms_message}")
        print(f"\n[{len(outreach.sms_message)} characters]")

        # Display Email
        print("\n" + "=" * 70)
        print("GENERATED EMAIL")
        print("=" * 70)
        print(f"\nSubject: {outreach.email_subject}")
        print("\nBody (plain text):")
        print("-" * 40)
        print(outreach.email_text)
        print("-" * 40)

        # Show HTML preview hint
        print("\nHTML body saved to: test_email_preview.html")

        # Save HTML for preview
        with open('test_email_preview.html', 'w') as f:
            f.write(f"""<!DOCTYPE html>
<html>
<head>
    <title>Email Preview - {first_name} {last_name}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; background: #f0f0f0; }}
        .preview {{ background: white; max-width: 600px; margin: 0 auto; padding: 40px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .meta {{ background: #f8f8f8; padding: 15px; margin-bottom: 20px; border-radius: 4px; }}
        .meta p {{ margin: 5px 0; font-size: 14px; color: #666; }}
    </style>
</head>
<body>
    <div class="preview">
        <div class="meta">
            <p><strong>To:</strong> {email}</p>
            <p><strong>Subject:</strong> {outreach.email_subject}</p>
            <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        {outreach.email_body}
    </div>
</body>
</html>""")

        # Ask to send
        if send:
            print("\n" + "=" * 70)
            print("SENDING...")
            print("=" * 70)

            # Send SMS
            from app.messaging.playwright_sms_service import PlaywrightSMSService
            from app.database.supabase_client import SupabaseClientSingleton
            from app.webhook.ai_webhook_handlers import resolve_organization_for_person, resolve_user_for_person
            from app.ai_agent.settings_service import get_fub_browser_credentials

            supabase = SupabaseClientSingleton.get_instance()
            org_id = await resolve_organization_for_person(person_id)
            user_id = await resolve_user_for_person(person_id, org_id)

            credentials = await get_fub_browser_credentials(
                supabase_client=supabase,
                user_id=user_id,
                organization_id=org_id,
            )

            if credentials and phone != 'N/A':
                print("\n   Sending SMS via Playwright...")
                sms_service = PlaywrightSMSService()
                agent_id = credentials.get("agent_id", user_id or "default")

                try:
                    result = await sms_service.send_text_message(
                        agent_id=agent_id,
                        person_id=person_id,
                        message=outreach.sms_message,
                        credentials=credentials,
                    )

                    if result.get('success'):
                        print("   [OK] SMS sent!")
                    else:
                        print(f"   [FAIL] SMS failed: {result.get('error')}")
                finally:
                    await sms_service.shutdown()
            else:
                print("   [SKIP] No credentials or phone number for SMS")

            # Send Email
            if email != 'N/A':
                print("\n   Sending EMAIL...")
                from app.email.ai_email_service import get_ai_email_service, EmailCategory

                email_service = get_ai_email_service()
                email_result = email_service.send_email(
                    to_email=email,
                    subject=outreach.email_subject,
                    html_content=outreach.email_body,
                    text_content=outreach.email_text,
                    from_email="adam@saahomes.com",
                    from_name="Adam Schwartz",
                    fub_person_id=person_id,
                    category=EmailCategory.WELCOME,
                    log_to_fub=True,
                )

                if email_result.success:
                    print("   [OK] Email sent!")
                else:
                    print(f"   [FAIL] Email failed: {email_result.error}")
            else:
                print("   [SKIP] No email address")

        else:
            print("\n" + "=" * 70)
            print("PREVIEW ONLY - Add --send flag to actually send")
            print("=" * 70)

    except Exception as e:
        print(f"\n   ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("Done!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test AI initial outreach')
    parser.add_argument('person_id', type=int, help='FUB person ID')
    parser.add_argument('--send', action='store_true', help='Actually send the messages')
    args = parser.parse_args()

    asyncio.run(test_outreach(args.person_id, args.send))
