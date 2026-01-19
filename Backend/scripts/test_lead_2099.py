#!/usr/bin/env python3
"""Quick test script for lead 2099."""

import os
import sys

# Add Backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database.fub_api_client import FUBApiClient

def main():
    api_client = FUBApiClient()
    person_id = 2099

    print("=" * 60)
    print("FETCHING LEAD 2099")
    print("=" * 60)

    lead_data = api_client.get_person(person_id)
    if not lead_data:
        print("Lead not found!")
        return

    print(f"ID: {lead_data.get('id')}")
    print(f"Name: {lead_data.get('firstName', 'N/A')} {lead_data.get('lastName', 'N/A')}")

    stage = lead_data.get('stage')
    if isinstance(stage, dict):
        print(f"Stage: {stage.get('name', 'N/A')}")
    else:
        print(f"Stage: {stage or 'N/A'}")

    print(f"Source: {lead_data.get('source', 'N/A')}")
    print(f"Type: {lead_data.get('type', 'N/A')}")
    print(f"Created: {lead_data.get('created', 'N/A')}")

    # Tags
    tags = lead_data.get('tags', [])
    if tags and isinstance(tags[0], dict):
        tag_names = [t.get('tag', '') for t in tags]
    else:
        tag_names = tags or []
    print(f"Tags: {tag_names}")

    # Contact info
    emails = lead_data.get('emails', [])
    phones = lead_data.get('phones', [])
    print(f"Email: {emails[0].get('value') if emails else 'N/A'}")
    print(f"Phone: {phones[0].get('value') if phones else 'N/A'}")

    print(f"Assigned To: {lead_data.get('assignedTo', 'Unassigned')}")

    # Address
    addresses = lead_data.get('addresses', [])
    if addresses:
        addr = addresses[0]
        print(f"Address: {addr.get('street', '')} {addr.get('city', '')} {addr.get('state', '')}")

    print()
    print("=" * 60)
    print("AI AGENT ANALYSIS")
    print("=" * 60)

    from app.ai_agent.response_generator import LeadProfile, AIResponseGenerator

    # Build lead profile
    lead_profile = LeadProfile.from_fub_data(lead_data)

    print(f"Lead Type (detected): {lead_profile.lead_type.upper() if lead_profile.lead_type else 'UNKNOWN'}")
    print(f"Days Since Created: {lead_profile.days_since_created}")

    # Initialize response generator
    response_generator = AIResponseGenerator(
        personality="friendly_casual",
        agent_name="Sarah",
        brokerage_name="SAA Homes"
    )

    # Goal section
    goal_section = response_generator._build_goal_section(lead_profile)
    print()
    print("GOAL SECTION:")
    for line in goal_section.strip().split('\n')[:4]:
        print(f"  {line}")

    # Source strategy
    strategy = response_generator._get_source_strategy(lead_profile.source)
    print()
    print(f"SOURCE STRATEGY ({lead_profile.source}):")
    print(f"  Approach: {strategy['approach']}")
    print(f"  Urgency: {strategy['urgency']}")

    # Lead status
    lead_status = response_generator._classify_lead_status(lead_profile)
    print()
    print(f"LEAD STATUS: {lead_status}")

    # Known info
    known_info = response_generator._build_known_info_section(lead_profile)
    print()
    print("KNOWN INFO:")
    if known_info:
        for line in known_info.split('\n')[:8]:
            if line.strip():
                print(f"  {line}")
    else:
        print("  (No known info)")

    return lead_data, lead_profile, response_generator


def test_send_sms(person_id: int, message: str):
    """Test sending an actual SMS via FUB."""
    import asyncio
    from app.messaging.fub_sms_service import FUBSMSServiceSingleton

    print()
    print("=" * 60)
    print("SENDING SMS TEST")
    print("=" * 60)
    print(f"To: Person ID {person_id}")
    print(f"Message: {message}")
    print(f"Length: {len(message)} chars")
    print()

    sms_service = FUBSMSServiceSingleton.get_instance()

    async def send():
        result = await sms_service.send_text_message_async(
            person_id=person_id,
            message=message,
        )
        return result

    result = asyncio.run(send())

    if result.get("success"):
        print("[SUCCESS] SMS sent!")
        print(f"  Message ID: {result.get('message_id')}")
    else:
        print("[FAILED] SMS send failed")
        print(f"  Error: {result.get('error')}")

    return result


def test_add_note(person_id: int, note_content: str):
    """Test adding a note to FUB."""
    from app.fub.note_service import get_note_service

    print()
    print("=" * 60)
    print("ADDING NOTE TEST")
    print("=" * 60)
    print(f"To: Person ID {person_id}")
    print(f"Note: {note_content[:100]}...")
    print()

    note_service = get_note_service()
    result = note_service.post_note_to_person(
        person_id=person_id,
        subject="AI Test Note",
        body=note_content,
        is_html=True,
    )

    if result and "error" not in result:
        print("[SUCCESS] Note added!")
        print(f"  Note ID: {result.get('id')}")
    else:
        print("[FAILED] Note add failed")
        print(f"  Error: {result}")

    return result


def test_create_task(person_id: int, description: str):
    """Test creating a task in FUB."""
    from datetime import datetime, timedelta
    from app.messaging.fub_sms_service import FUBSMSServiceSingleton

    print()
    print("=" * 60)
    print("CREATING TASK TEST")
    print("=" * 60)
    print(f"For: Person ID {person_id}")
    print(f"Description: {description}")
    print()

    sms_service = FUBSMSServiceSingleton.get_instance()
    due_date = datetime.now() + timedelta(hours=4)

    result = sms_service.create_task(
        person_id=person_id,
        description=description,
        due_date=due_date,
    )

    if result and result.get("success"):
        print("[SUCCESS] Task created!")
        print(f"  Task ID: {result.get('task_id')}")
    else:
        print("[FAILED] Task creation failed")
        print(f"  Error: {result}")

    return result


def test_playwright_sms(person_id: int, message: str, credentials: dict):
    """Test sending SMS via Playwright browser automation."""
    import asyncio
    from app.messaging.playwright_sms_service import PlaywrightSMSServiceSingleton

    print()
    print("=" * 60)
    print("PLAYWRIGHT SMS TEST")
    print("=" * 60)
    print(f"To: Person ID {person_id}")
    print(f"Message: {message}")
    print(f"Login Type: {credentials.get('type', 'email')}")
    print(f"Email: {credentials.get('email', 'N/A')}")
    print()

    async def send():
        service = await PlaywrightSMSServiceSingleton.get_instance()
        # Use a default agent ID for testing
        agent_id = credentials.get("agent_id", "test_agent")
        result = await service.send_sms(
            agent_id=agent_id,
            person_id=person_id,
            message=message,
            credentials=credentials
        )
        return result

    result = asyncio.run(send())

    if result.get("success"):
        print("[SUCCESS] SMS sent via Playwright!")
        print(f"  Message ID: {result.get('message_id')}")
    else:
        print("[FAILED] Playwright SMS send failed")
        print(f"  Error: {result.get('error')}")

    return result


def test_playwright_sms_auto(person_id: int, message: str):
    """Test sending SMS via Playwright with auto credential lookup."""
    import asyncio
    from app.messaging.playwright_sms_service import send_sms_with_auto_credentials

    print()
    print("=" * 60)
    print("PLAYWRIGHT SMS TEST (AUTO CREDENTIALS)")
    print("=" * 60)
    print(f"To: Person ID {person_id}")
    print(f"Message: {message}")
    print("Credentials: Auto-loaded from settings/env")
    print()

    async def send():
        result = await send_sms_with_auto_credentials(
            person_id=person_id,
            message=message,
        )
        return result

    result = asyncio.run(send())

    if result.get("success"):
        print("[SUCCESS] SMS sent via Playwright!")
        print(f"  Message ID: {result.get('message_id')}")
    else:
        print("[FAILED] Playwright SMS send failed")
        print(f"  Error: {result.get('error')}")

    return result


if __name__ == "__main__":
    import sys

    lead_data, lead_profile, response_generator = main()

    args = sys.argv[1:]
    person_id = lead_data.get("id")
    first_name = lead_data.get("firstName", "there")

    # Check for --playwright flag for browser-based SMS
    if "--playwright" in args:
        print()
        print("=" * 60)
        print("PLAYWRIGHT SMS TEST")
        print("=" * 60)

        test_message = f"Hey {first_name}! Just checking in - still thinking about finding a place in the Greeley area?"

        # Use auto-credentials (from env or db settings)
        test_playwright_sms_auto(person_id, test_message)

        print()
        print("=" * 60)
        print("PLAYWRIGHT TEST COMPLETE")
        print("=" * 60)

    # Check if we should run live API tests
    elif "--live" in args:
        print()
        print("=" * 60)
        print("RUNNING LIVE API TESTS")
        print("=" * 60)

        # Re-engagement message for dormant buyer
        test_message = f"Hey {first_name}! Just checking in - still thinking about finding a place in the Greeley area?"

        # Test SMS (API - logs only, doesn't actually send)
        test_send_sms(person_id, test_message)

        # Test Note
        test_note = f"""
        <p><strong>AI Re-engagement Test</strong></p>
        <p>Lead status: dormant_reengaging (476 days)</p>
        <p>Lead type: BUYER</p>
        <p>Goal: Book a SHOWING APPOINTMENT</p>
        <p><small>This is a test note from the AI agent system.</small></p>
        """
        test_add_note(person_id, test_note)

        # Test Task
        test_task = f"AI SHOWING APPOINTMENT - {first_name}\nRe-engaged dormant buyer. Follow up to schedule showings."
        test_create_task(person_id, test_task)

        print()
        print("=" * 60)
        print("LIVE API TESTS COMPLETE")
        print("=" * 60)
    else:
        print()
        print("Usage:")
        print("  python scripts/test_lead_2099.py              # Analysis only")
        print("  python scripts/test_lead_2099.py --live       # API tests (note, task - SMS logs only)")
        print("  python scripts/test_lead_2099.py --playwright # Browser-based SMS (actually sends!)")
        print()
        print("For --playwright, credentials are loaded from:")
        print("  1. Database ai_agent_settings (fub_login_email, fub_login_password)")
        print("  2. Environment variables (FUB_LOGIN_EMAIL, FUB_LOGIN_PASSWORD)")
        print()
        print("Set in .env file:")
        print("  FUB_LOGIN_EMAIL=your@email.com")
        print("  FUB_LOGIN_PASSWORD=yourpassword")
        print("  FUB_LOGIN_TYPE=email  # or 'google' or 'microsoft'")
