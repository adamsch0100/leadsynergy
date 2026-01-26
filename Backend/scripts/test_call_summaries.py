"""Test script to fetch call summaries from FUB via Playwright.

This script fetches FUB browser credentials from the database and uses
Playwright to scrape call summaries from the FUB UI (not available via API).
"""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def get_credentials_from_db():
    """Get FUB browser credentials from database."""
    from app.database.supabase_client import SupabaseClientSingleton
    from app.ai_agent.settings_service import get_fub_browser_credentials

    try:
        supabase = SupabaseClientSingleton.get_instance()
        credentials = await get_fub_browser_credentials(supabase_client=supabase)

        if credentials:
            print(f"  FUB Login: {credentials.get('email', 'N/A')}")
            print(f"  Login Type: {credentials.get('type', 'email')}")
            return credentials
        else:
            print("  ERROR: No FUB browser credentials found in database or env")
            return None
    except Exception as e:
        print(f"  ERROR getting credentials: {e}")
        return None


async def test_call_summaries(person_id: int):
    """Test fetching call summaries for a person."""
    from app.messaging.playwright_sms_service import PlaywrightSMSServiceSingleton

    print(f"\n{'='*60}")
    print(f"  Testing Call Summary Scraping for Person {person_id}")
    print(f"{'='*60}\n")

    print("1. Getting credentials from database...")
    credentials = await get_credentials_from_db()

    if not credentials:
        return {"success": False, "error": "No credentials"}

    print("\n2. Initializing Playwright service...")
    service = await PlaywrightSMSServiceSingleton.get_instance()

    print(f"\n3. Fetching call summaries for person {person_id}...")
    agent_id = credentials.get("agent_id", "default_agent")
    result = await service.read_call_summaries(agent_id, person_id, credentials, limit=5)

    if result.get("success"):
        summaries = result.get("summaries", [])
        print(f"\nFound {len(summaries)} call summaries:\n")

        for i, summary in enumerate(summaries, 1):
            print(f"--- Call {i} ---")
            if summary.get("caller"):
                print(f"  From: {summary.get('caller')} -> {summary.get('recipient')}")
            if summary.get("duration"):
                print(f"  Duration: {summary.get('duration')}")
            if summary.get("timestamp"):
                print(f"  Time: {summary.get('timestamp')}")
            if summary.get("summary"):
                print(f"  Summary: {summary.get('summary')}")
            print()
    else:
        print(f"\nFailed to get call summaries: {result.get('error')}")

    return result


async def get_full_context(person_id: int):
    """Get full context for a person including API data and scraped call summaries."""
    from app.database.fub_api_client import FUBApiClient
    from app.ai_agent.response_generator import LeadProfile
    from app.messaging.playwright_sms_service import PlaywrightSMSServiceSingleton

    print(f"\n{'='*60}")
    print(f"  Full Context for Person {person_id}")
    print(f"{'='*60}\n")

    # Get credentials first
    print("0. Getting credentials from database...")
    credentials = await get_credentials_from_db()

    if not credentials:
        print("   Cannot proceed without credentials")
        return None

    # Get FUB API data (sync methods)
    fub_client = FUBApiClient()

    print("\n1. Fetching person data from FUB API...")
    person = fub_client.get_person(person_id)
    if not person:
        print(f"   ERROR: Could not fetch person {person_id}")
        return None

    name = f"{person.get('firstName', '')} {person.get('lastName', '')}".strip()
    print(f"   Name: {name}")
    print(f"   Source: {person.get('source', 'Unknown')}")
    print(f"   Score: {person.get('score', 0)}")

    # Get calls from API
    print("\n2. Fetching calls from FUB API...")
    calls = fub_client.get_calls_for_person(person_id)
    print(f"   Found {len(calls)} calls in API")

    # Get emails from API
    print("\n3. Fetching emails from FUB API...")
    emails = fub_client.get_emails_for_person(person_id)
    print(f"   Found {len(emails)} emails in API")

    # Get text messages from API
    print("\n4. Fetching text messages from FUB API...")
    texts = fub_client.get_text_messages_for_person(person_id)
    print(f"   Found {len(texts)} text messages in API")

    # Get call summaries via Playwright (not in API!)
    print("\n5. Fetching call summaries via Playwright (scraping)...")
    service = await PlaywrightSMSServiceSingleton.get_instance()
    agent_id = credentials.get("agent_id", "default_agent")
    call_summary_result = await service.read_call_summaries(agent_id, person_id, credentials, limit=5)

    scraped_summaries = []
    if call_summary_result.get("success"):
        scraped_summaries = call_summary_result.get("summaries", [])
        print(f"   Found {len(scraped_summaries)} call summaries via scraping")
        for s in scraped_summaries:
            if s.get("summary"):
                print(f"   - {s.get('summary')[:100]}...")
    else:
        print(f"   Could not scrape call summaries: {call_summary_result.get('error')}")

    # Get text message history via Playwright (API hides message body)
    print("\n5b. Fetching text message history via Playwright (scraping)...")
    text_history_result = await service.read_recent_messages(agent_id, person_id, credentials, limit=15)

    scraped_messages = []
    if text_history_result.get("success"):
        scraped_messages = text_history_result.get("messages", [])
        print(f"   Found {len(scraped_messages)} entries via scraping")

        # Count by type
        texts = [m for m in scraped_messages if m.get("entry_type") == "text"]
        notes = [m for m in scraped_messages if m.get("entry_type") == "action_plan_note"]
        calls = [m for m in scraped_messages if m.get("entry_type") == "call"]
        emails = [m for m in scraped_messages if m.get("entry_type") == "email"]

        print(f"   -> {len(texts)} actual texts, {len(notes)} action plan notes, {len(calls)} calls, {len(emails)} emails")

        for m in scraped_messages[:8]:
            direction = "IN" if m.get("is_incoming") else "OUT"
            entry_type = m.get("entry_type", "?")
            has_phone = m.get("debug_has_phone_icon", "?")
            has_bubble = m.get("debug_has_bubble_icon", "?")
            header = m.get("debug_header_area", "")[:30]
            print(f"   - [{entry_type.upper():15}] [{direction}] {m.get('text', '')[:35]}...")
            print(f"        phone:{has_phone}, bubble:{has_bubble}, header:'{header}'")
    else:
        print(f"   Could not scrape messages: {text_history_result.get('error')}")

    # Build FUB context
    print("\n6. Building AI context...")
    fub_context = {
        "person": person,
        "calls": calls,
        "emails": emails,
        "textMessages": texts,
    }

    # Process FUB context into additional_data, then create LeadProfile
    additional_data = LeadProfile.process_fub_context(fub_context)

    # Add scraped call summaries to additional_data before creating profile
    if scraped_summaries:
        formatted_summaries = []
        for s in scraped_summaries:
            if s.get("summary"):
                duration_str = f" ({s.get('duration')})" if s.get('duration') else ""
                formatted_summaries.append(f"[Call{duration_str}]: {s.get('summary')}")

        # Merge with any existing call_summaries from API
        if additional_data.get("call_summaries"):
            additional_data["call_summaries"].extend(formatted_summaries)
        else:
            additional_data["call_summaries"] = formatted_summaries

    # Add scraped text messages to additional_data
    # Only count actual texts (not action plan notes) for message counts
    if scraped_messages:
        # Separate actual texts from action plan notes
        actual_texts = [m for m in scraped_messages if m.get("entry_type") == "text"]
        action_plan_notes = [m for m in scraped_messages if m.get("entry_type") == "action_plan_note"]

        # Format actual text conversation history
        formatted_messages = []
        for m in actual_texts:
            direction = "LEAD" if m.get("is_incoming") else "AGENT"
            text = m.get("text", "")[:200]
            formatted_messages.append(f"[{direction}]: {text}")

        # Also add action plan notes as context (but marked differently)
        for m in action_plan_notes:
            text = m.get("text", "")[:200]
            formatted_messages.append(f"[ACTION_PLAN_NOTE]: {text}")

        additional_data["conversation_history"] = formatted_messages
        # Only count actual texts for message counts
        additional_data["total_messages_sent"] = sum(1 for m in actual_texts if not m.get("is_incoming"))
        additional_data["total_messages_received"] = sum(1 for m in actual_texts if m.get("is_incoming"))

    # Create LeadProfile from person data + additional context
    lead_profile = LeadProfile.from_fub_data(person, additional_data)

    # Generate context string
    context_string = lead_profile.to_context_string()

    print("\n" + "="*60)
    print("  FULL AI CONTEXT STRING")
    print("="*60)
    print(context_string)
    print("="*60)

    return lead_profile


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Test call summary scraping")
    parser.add_argument("--person", "-p", type=int, default=3291, help="Person ID to test (default: 3291 Jesus)")
    parser.add_argument("--full", "-f", action="store_true", help="Get full context including API data")
    args = parser.parse_args()

    if args.full:
        await get_full_context(args.person)
    else:
        await test_call_summaries(args.person)

    # Cleanup
    from app.messaging.playwright_sms_service import PlaywrightSMSServiceSingleton
    await PlaywrightSMSServiceSingleton.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
