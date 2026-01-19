# -*- coding: utf-8 -*-
"""
AI Agent Testing Script - Tests the full AI agent pipeline.

Usage:
    python -m scripts.test_ai_agent                    # Test with default lead (2099)
    python -m scripts.test_ai_agent --lead 3277        # Test with specific lead
    python -m scripts.test_ai_agent --lead 2099 --send # Actually send SMS (careful!)
"""

import argparse
import asyncio
import os
import sys
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test the AI Agent pipeline")
    parser.add_argument("--lead", type=int, default=2099,
                        help="FUB Person ID to test with (default: 2099)")
    parser.add_argument("--send", action="store_true",
                        help="Actually send the SMS (USE WITH CAUTION)")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Generate response without sending (default)")
    return parser.parse_args()


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print test result."""
    status = "[PASS]" if passed else "[FAIL]"
    print(f"\n{status}: {test_name}")
    if details:
        print(f"   {details}")


async def test_fub_credentials():
    """Test 1: Verify FUB login credentials are configured."""
    print_section("Test 1: FUB Credentials Check")

    from app.ai_agent.settings_service import get_fub_browser_credentials
    from app.database.supabase_client import SupabaseClientSingleton

    supabase = SupabaseClientSingleton.get_instance()

    # Check for credentials in database
    credentials = await get_fub_browser_credentials(supabase_client=supabase)

    if credentials:
        print_result("FUB browser credentials found", True)
        print(f"   Email: {credentials.get('email', 'N/A')}")
        print(f"   Login type: {credentials.get('type', 'email')}")
        print(f"   Password configured: {'Yes' if credentials.get('password') else 'No'}")
        return True
    else:
        # Check environment variables as fallback
        env_email = os.getenv("FUB_LOGIN_EMAIL")
        env_pass = os.getenv("FUB_LOGIN_PASSWORD")

        if env_email and env_pass:
            print_result("FUB browser credentials found (from environment)", True)
            print(f"   Email: {env_email}")
            return True
        else:
            print_result("FUB browser credentials NOT found", False,
                        "Set FUB_LOGIN_EMAIL and FUB_LOGIN_PASSWORD in .env or database")

            # Check if FUB API key exists at least
            fub_api_key = os.getenv("FUB_API_KEY") or os.getenv("FOLLOWUPBOSS_API_KEY")
            if fub_api_key:
                print(f"\n   NOTE: FUB_API_KEY is present (for API calls)")
                print(f"   But FUB_LOGIN_EMAIL/PASSWORD needed for Playwright SMS")
            return False


async def test_llm_api_keys():
    """Test: Verify LLM API keys are configured."""
    print_section("Test 1b: LLM API Keys Check")

    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if openrouter_key:
        masked = openrouter_key[:15] + "..." + openrouter_key[-4:] if len(openrouter_key) > 20 else "***"
        print_result("OpenRouter API key found", True, f"Key: {masked}")
        print(f"   Using model: xiaomi/mimo-v2-flash:free")
        return True
    elif anthropic_key:
        masked = anthropic_key[:10] + "..." + anthropic_key[-4:] if len(anthropic_key) > 20 else "***"
        print_result("Anthropic API key found", True, f"Key: {masked}")
        return True
    else:
        print_result("No LLM API key found", False,
                    "Add OPENROUTER_API_KEY or ANTHROPIC_API_KEY to .env file")
        return False


async def test_load_lead_profile(fub_person_id: int = 3277):
    """Test 2: Load lead profile from FUB."""
    print_section(f"Test 2: Load Lead Profile (FUB Person ID: {fub_person_id})")

    from app.database.fub_api_client import FUBApiClient

    # Get FUB API key
    fub_api_key = os.getenv("FUB_API_KEY") or os.getenv("FOLLOWUPBOSS_API_KEY")

    if not fub_api_key:
        print_result("FUB API key check", False, "No FUB_API_KEY in environment")
        return None

    print_result("FUB API key found", True)

    client = FUBApiClient(api_key=fub_api_key)

    try:
        person = client.get_person(fub_person_id)

        if person:
            print_result("Lead profile loaded", True)
            print(f"\n   LEAD PROFILE:")
            print(f"   Name: {person.get('firstName', '')} {person.get('lastName', '')}")
            print(f"   Source: {person.get('source', 'Unknown')}")
            stage = person.get('stage')
            if isinstance(stage, dict):
                stage_name = stage.get('name', 'Unknown')
            elif isinstance(stage, str):
                stage_name = stage
            else:
                stage_name = 'Unknown'
            print(f"   Stage: {stage_name}")

            # Get emails and phones
            emails = person.get('emails', [])
            phones = person.get('phones', [])
            print(f"   Email: {emails[0].get('value', 'N/A') if emails else 'N/A'}")
            print(f"   Phone: {phones[0].get('value', 'N/A') if phones else 'N/A'}")

            # Get tags
            tags = person.get('tags', [])
            tag_names = []
            if tags:
                if isinstance(tags[0], dict):
                    tag_names = [t.get('tag', '') for t in tags]
                else:
                    tag_names = list(tags)
                print(f"   Tags: {', '.join(tag_names[:5])}")

            # Get assigned user
            assigned = person.get('assignedUser', {})
            print(f"   Assigned to: {assigned.get('name', 'Unassigned') if assigned else 'Unassigned'}")

            # Get created date
            created = person.get('created', '')
            print(f"   Created: {created[:10] if created else 'Unknown'}")

            # Check lead type from tags
            lead_type = "Unknown"
            for tag in tag_names:
                tag_lower = tag.lower()
                if 'buyer' in tag_lower:
                    lead_type = "Buyer"
                    break
                elif 'seller' in tag_lower:
                    lead_type = "Seller"
                    break
            print(f"   Lead Type: {lead_type}")

            return person
        else:
            print_result("Lead profile loaded", False, "Person not found")
            return None

    except Exception as e:
        print_result("Lead profile loaded", False, f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def test_ai_agent_settings():
    """Test 3: Verify AI agent settings."""
    print_section("Test 3: AI Agent Settings Check")

    from app.ai_agent.settings_service import get_agent_settings
    from app.database.supabase_client import SupabaseClientSingleton

    try:
        supabase = SupabaseClientSingleton.get_instance()
        settings = await get_agent_settings(supabase_client=supabase)

        print_result("AI Agent settings loaded", True)
        print(f"\n   SETTINGS:")
        print(f"   Agent name: {settings.agent_name}")
        print(f"   Brokerage: {settings.brokerage_name}")
        print(f"   Personality: {settings.personality_tone}")
        print(f"   AI Enabled: {settings.is_enabled}")
        print(f"   Working hours: {settings.working_hours_start} - {settings.working_hours_end}")
        print(f"   Timezone: {settings.timezone}")
        print(f"   Max response length: {settings.max_response_length} chars")
        print(f"   Auto-schedule threshold: {settings.auto_schedule_score_threshold}")
        print(f"   Auto-handoff score: {settings.auto_handoff_score}")

        # Check if FUB browser credentials are in settings
        if settings.fub_login_email:
            print(f"\n   FUB Browser Login:")
            print(f"   Email: {settings.fub_login_email}")
            print(f"   Type: {settings.fub_login_type}")
            print(f"   Password set: {'Yes' if settings.fub_login_password else 'No'}")

        return settings

    except Exception as e:
        print_result("AI Agent settings loaded", False, f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def test_generate_ai_response(fub_person_id: int = 3277, lead_data: dict = None):
    """Test 4: Generate an AI response for the lead (without sending)."""
    print_section(f"Test 4: Generate AI Response (FUB Person ID: {fub_person_id})")

    # Check for any LLM API key
    has_openrouter = os.getenv("OPENROUTER_API_KEY")
    has_anthropic = os.getenv("ANTHROPIC_API_KEY")
    if not has_openrouter and not has_anthropic:
        print_result("AI Response generated", False, "No LLM API key set (OPENROUTER or ANTHROPIC)")
        return None

    from app.ai_agent.response_generator import AIResponseGenerator, LeadProfile
    from app.ai_agent.settings_service import get_agent_settings
    from app.database.supabase_client import SupabaseClientSingleton

    try:
        supabase = SupabaseClientSingleton.get_instance()
        settings = await get_agent_settings(supabase_client=supabase)

        # Initialize response generator with settings
        generator = AIResponseGenerator(
            personality=settings.personality_tone,
            agent_name=settings.agent_name,
            brokerage_name=settings.brokerage_name,
            llm_provider=settings.llm_provider,
            llm_model=settings.llm_model,
            llm_model_fallback=settings.llm_model_fallback,
        )

        # Build lead profile from FUB data
        if lead_data:
            profile = LeadProfile.from_fub_data(lead_data)
            profile.fub_person_id = fub_person_id
        else:
            # Create minimal profile
            profile = LeadProfile(
                first_name="Test",
                last_name="Lead",
                source="MyAgentFinder",
                fub_person_id=fub_person_id,
            )

        print(f"\n   Lead context being sent to AI:")
        print("-" * 40)
        context_str = profile.to_context_string()
        lines = context_str.split('\n')
        for line in lines[:20]:
            print(f"   {line}")
        if len(lines) > 20:
            print(f"   ... ({len(lines) - 20} more lines)")
        print("-" * 40)

        # Build lead_context dict for the API
        lead_context = {
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "source": profile.source,
            "lead_type": profile.lead_type,
            "score": profile.score,
        }

        # Generate response to a simulated lead message
        # (First contact uses templates, not LLM - so we simulate a lead reply)
        test_message = "Hi, yes I'm looking to buy a home"
        print(f"\n   Simulating lead message: \"{test_message}\"")
        print("   Generating AI response...")

        response = await generator.generate_response(
            incoming_message=test_message,
            conversation_history=[],
            lead_context=lead_context,
            current_state="initial",
            qualification_data={},
            lead_profile=profile,
        )

        print_result("AI Response generated", True)
        print(f"\n   AI RESPONSE:")
        print(f"   Message: \"{response.response_text}\"")
        print(f"   Length: {len(response.response_text)} chars (limit: 160)")
        print(f"   Next state: {response.next_state}")
        print(f"   Intent: {response.detected_intent}")
        print(f"   Confidence: {response.confidence:.2f}")
        print(f"   Lead score delta: {response.lead_score_delta:+d}")
        print(f"   Quality: {response.quality.value}")
        if response.warnings:
            print(f"   Warnings: {response.warnings}")

        return response

    except Exception as e:
        print_result("AI Response generated", False, f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def test_simulated_conversation(fub_person_id: int = 3277, lead_data: dict = None):
    """Test 5: Simulate a multi-turn conversation."""
    print_section("Test 5: Simulated Conversation Flow")

    # Check for any LLM API key
    has_openrouter = os.getenv("OPENROUTER_API_KEY")
    has_anthropic = os.getenv("ANTHROPIC_API_KEY")
    if not has_openrouter and not has_anthropic:
        print_result("Simulated conversation", False, "No LLM API key set")
        return

    from app.ai_agent.response_generator import AIResponseGenerator, LeadProfile
    from app.ai_agent.settings_service import get_agent_settings
    from app.database.supabase_client import SupabaseClientSingleton

    try:
        supabase = SupabaseClientSingleton.get_instance()
        settings = await get_agent_settings(supabase_client=supabase)

        generator = AIResponseGenerator(
            personality=settings.personality_tone,
            agent_name=settings.agent_name,
            brokerage_name=settings.brokerage_name,
            llm_provider=settings.llm_provider,
            llm_model=settings.llm_model,
            llm_model_fallback=settings.llm_model_fallback,
        )

        if lead_data:
            profile = LeadProfile.from_fub_data(lead_data)
            profile.fub_person_id = fub_person_id
        else:
            profile = LeadProfile(
                first_name="Test",
                last_name="Lead",
                source="MyAgentFinder",
                fub_person_id=fub_person_id,
            )

        # Simulated conversation turns (skip empty first contact - uses templates)
        conversation_turns = [
            "Hi, yes I'm looking to buy a home in the Sacramento area",
            "We want to move in about 60 days",
            "Our budget is around $450k, maybe up to $500k",
        ]

        # Build lead_context dict for the API
        lead_context = {
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "source": profile.source,
            "lead_type": profile.lead_type,
            "score": profile.score,
        }

        conversation_history = []
        current_state = "initial"
        qualification_data = {}
        lead_score = 0

        print("\n   SIMULATED CONVERSATION:")
        print("-" * 50)

        for i, lead_message in enumerate(conversation_turns):
            print(f"\n   LEAD: \"{lead_message}\"")
            conversation_history.append({
                "role": "lead",
                "direction": "inbound",
                "content": lead_message,
                "timestamp": datetime.utcnow().isoformat()
            })

            response = await generator.generate_response(
                incoming_message=lead_message,
                conversation_history=conversation_history,
                lead_context=lead_context,
                current_state=current_state,
                qualification_data=qualification_data,
                lead_profile=profile,
            )

            # Update state
            current_state = response.next_state or current_state
            lead_score += response.lead_score_delta
            if response.extracted_info:
                qualification_data.update({k: v for k, v in response.extracted_info.items() if v})

            print(f"   AGENT: \"{response.response_text}\"")
            extracted = {k: v for k, v in response.extracted_info.items() if v} if response.extracted_info else {}
            print(f"   [State: {current_state}, Score: {lead_score:+d}]")
            if extracted:
                print(f"   [Extracted: {extracted}]")

            conversation_history.append({
                "role": "agent",
                "content": response.response_text,
                "timestamp": datetime.utcnow().isoformat()
            })

        print("-" * 50)
        print(f"\n   FINAL STATE: {current_state}")
        print(f"   TOTAL SCORE: {lead_score:+d}")
        print(f"   QUALIFICATION DATA: {json.dumps(qualification_data, indent=4)}")

    except Exception as e:
        print_result("Simulated conversation", False, f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_send_sms(fub_person_id: int, message: str, lead_data: dict = None):
    """Test 6: Actually send an SMS via Playwright (USE WITH CAUTION)."""
    print_section(f"Test 6: SEND SMS to Lead #{fub_person_id}")

    print(f"\n   WARNING: This will send a REAL SMS to the lead!")
    print(f"   Message: \"{message}\"")
    print(f"   Length: {len(message)} chars")

    # Get phone number
    phones = lead_data.get('phones', []) if lead_data else []
    phone = phones[0].get('value', 'N/A') if phones else 'N/A'
    print(f"   To: {phone}")

    if phone == 'N/A':
        print_result("SMS Send", False, "No phone number found for lead")
        return False

    try:
        from app.messaging.playwright_sms_service import send_sms_with_auto_credentials
        from app.database.supabase_client import SupabaseClientSingleton

        supabase = SupabaseClientSingleton.get_instance()

        print("\n   Initializing Playwright browser session...")
        print("   TIP: Set PLAYWRIGHT_HEADLESS=false to see the browser window")
        result = await send_sms_with_auto_credentials(
            person_id=fub_person_id,
            message=message,
            supabase_client=supabase,
        )

        if result.get('success'):
            print_result("SMS Sent", True, f"Message delivered to {phone}")
            return True
        else:
            error = result.get('error', 'Unknown error')
            print_result("SMS Send", False, f"Failed: {error}")
            return False

    except ImportError as e:
        print_result("SMS Send", False, f"Playwright service not available: {e}")
        return False
    except Exception as e:
        print_result("SMS Send", False, f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def generate_first_contact_message(fub_person_id: int, lead_data: dict = None):
    """Generate a first-contact SMS message for the lead."""
    print_section(f"Generating First Contact Message for Lead #{fub_person_id}")

    from app.ai_agent.response_generator import AIResponseGenerator, LeadProfile
    from app.ai_agent.settings_service import get_agent_settings
    from app.database.supabase_client import SupabaseClientSingleton

    try:
        supabase = SupabaseClientSingleton.get_instance()
        settings = await get_agent_settings(supabase_client=supabase)

        generator = AIResponseGenerator(
            personality=settings.personality_tone,
            agent_name=settings.agent_name,
            brokerage_name=settings.brokerage_name,
            llm_provider=settings.llm_provider,
            llm_model=settings.llm_model,
            llm_model_fallback=settings.llm_model_fallback,
        )

        if lead_data:
            profile = LeadProfile.from_fub_data(lead_data)
            profile.fub_person_id = fub_person_id
        else:
            profile = LeadProfile(
                first_name="Lead",
                source="Unknown",
                fub_person_id=fub_person_id,
            )

        # Build lead_context dict
        lead_context = {
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "source": profile.source,
            "lead_type": profile.lead_type,
            "score": profile.score,
        }

        print(f"\n   Lead: {profile.first_name} {profile.last_name or ''}")
        print(f"   Source: {profile.source}")
        print(f"   Agent: {settings.agent_name}")
        print(f"   Personality: {settings.personality_tone}")

        # Generate FIRST contact response (no prior conversation)
        response = await generator.generate_response(
            incoming_message="",  # Empty for first contact
            conversation_history=[],
            lead_context=lead_context,
            current_state="initial",
            qualification_data={},
            lead_profile=profile,
        )

        print_result("First contact message generated", True)
        print(f"\n   MESSAGE: \"{response.response_text}\"")
        print(f"   Length: {len(response.response_text)} chars")

        return response.response_text

    except Exception as e:
        print_result("First contact message", False, f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run all tests."""
    args = parse_args()
    fub_person_id = args.lead
    should_send = args.send

    print("\n" + "=" * 60)
    print("  AI AGENT TESTING SUITE")
    print(f"  Lead: #{fub_person_id}")
    if should_send:
        print("  MODE: LIVE SEND (SMS will be sent!)")
    else:
        print("  MODE: DRY RUN (no messages sent)")
    print("=" * 60)

    # Test 1: FUB Credentials
    creds_ok = await test_fub_credentials()

    # Test 1b: LLM API Keys (OpenRouter or Anthropic)
    llm_ok = await test_llm_api_keys()

    # Test 2: Load Lead Profile
    lead_data = await test_load_lead_profile(fub_person_id)

    # Test 3: AI Settings
    settings = await test_ai_agent_settings()

    # Test 4: Generate Response
    if llm_ok and lead_data:
        response = await test_generate_ai_response(fub_person_id, lead_data)
    elif not llm_ok:
        print("\n[SKIP] Skipping response generation - no LLM API key")
    else:
        print("\n[SKIP] Skipping response generation - no lead data")

    # Test 5: Simulated Conversation
    if llm_ok and lead_data:
        await test_simulated_conversation(fub_person_id, lead_data)
    else:
        print("\n[SKIP] Skipping simulated conversation")

    # Test 6: Generate and optionally send first contact SMS
    if should_send and creds_ok and llm_ok and lead_data:
        print_section("LIVE SMS TEST")

        # Generate first contact message
        message = await generate_first_contact_message(fub_person_id, lead_data)

        if message:
            print(f"\n   Ready to send: \"{message}\"")
            confirm = input("\n   Type 'YES' to send this SMS: ")

            if confirm.strip().upper() == 'YES':
                await test_send_sms(fub_person_id, message, lead_data)
            else:
                print("\n   [CANCELLED] SMS not sent.")
    elif should_send:
        print("\n[SKIP] Cannot send SMS - missing credentials, API key, or lead data")

    print("\n" + "=" * 60)
    print("  TESTING COMPLETE")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
