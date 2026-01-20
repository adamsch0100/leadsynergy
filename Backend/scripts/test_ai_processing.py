"""
Test the AI agent processing directly (bypasses webhook layer).
This tests the actual message processing flow.
"""
import asyncio
import os
import sys
import logging

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Setup logging to see all output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)

# Add Backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Check required env vars
print("Checking environment variables...")
required_vars = ['SUPABASE_URL', 'SUPABASE_KEY', 'FUB_API_KEY', 'OPENROUTER_API_KEY']
missing = [v for v in required_vars if not os.getenv(v)]
if missing:
    print(f"ERROR: Missing environment variables: {missing}")
    sys.exit(1)
print(f"  [OK] All required env vars present (using OpenRouter)")

async def test_ai_processing():
    """Test the AI processing flow directly."""
    print("=" * 70)
    print("Testing AI Agent Processing Directly")
    print("=" * 70)
    
    # Import after path setup
    from app.database.supabase_client import SupabaseClientSingleton
    from app.database.fub_api_client import FUBApiClient
    
    supabase = SupabaseClientSingleton.get_instance()
    fub_client = FUBApiClient()
    
    # Use a real FUB person ID for testing
    PERSON_ID = 2099  # Change this to a test lead
    
    print(f"\n1. Getting person data from FUB for person {PERSON_ID}...")
    try:
        person_data = fub_client.get_person(PERSON_ID)
        print(f"   [OK] Got person: {person_data.get('firstName')} {person_data.get('lastName')}")
    except Exception as e:
        print(f"   [FAIL] Failed to get person: {e}")
        return
    
    print(f"\n2. Resolving organization...")
    from app.webhook.ai_webhook_handlers import resolve_organization_for_person, resolve_user_for_person
    organization_id = await resolve_organization_for_person(PERSON_ID)
    user_id = await resolve_user_for_person(PERSON_ID, organization_id)
    print(f"   Organization: {organization_id}")
    print(f"   User: {user_id}")
    
    if not organization_id or not user_id:
        print("   [FAIL] Could not resolve org/user")
        return
    
    print(f"\n3. Loading AI agent settings...")
    from app.ai_agent.settings_service import get_agent_settings
    settings = await get_agent_settings(supabase, organization_id)
    print(f"   Timezone: {settings.timezone if settings else 'N/A'}")
    print(f"   Agent Name: {settings.agent_name if settings else 'N/A'}")
    
    print(f"\n4. Checking compliance...")
    from app.ai_agent.compliance_checker import ComplianceChecker
    compliance_checker = ComplianceChecker(supabase_client=supabase)
    phone = person_data.get('phones', [{}])[0].get('value', '')
    timezone = settings.timezone if settings else "America/Denver"
    
    compliance_result = await compliance_checker.check_sms_compliance(
        fub_person_id=PERSON_ID,
        organization_id=organization_id,
        phone_number=phone,
        recipient_timezone=timezone,
    )
    print(f"   Can Send: {compliance_result.can_send}")
    print(f"   Reason: {compliance_result.reason or 'OK'}")
    
    if not compliance_result.can_send:
        print("\n   [WARN] Compliance blocked - stopping here")
        return
    
    print(f"\n5. Building lead profile...")
    from app.webhook.ai_webhook_handlers import build_lead_profile_from_fub
    lead_profile = await build_lead_profile_from_fub(person_data, organization_id)
    print(f"   Name: {lead_profile.first_name} {lead_profile.last_name}")
    print(f"   Source: {lead_profile.source}")
    
    print(f"\n6. Getting conversation history...")
    from app.webhook.ai_webhook_handlers import get_conversation_history
    history = await get_conversation_history(PERSON_ID, limit=15)
    print(f"   Messages: {len(history) if history else 0}")
    
    print(f"\n7. Getting conversation context...")
    from app.ai_agent.conversation_manager import ConversationManager
    conv_manager = ConversationManager(supabase_client=supabase)
    context = await conv_manager.get_or_create_conversation(
        fub_person_id=PERSON_ID,
        user_id=user_id,
        organization_id=organization_id,
        lead_data=person_data,
    )
    print(f"   State: {context.state}")
    print(f"   Conversation ID: {context.conversation_id}")
    
    print(f"\n8. Processing through AI Agent Service...")
    from app.webhook.ai_webhook_handlers import get_agent_service
    agent_service = get_agent_service()
    
    test_message = "Hello, I'm interested in buying a home"
    print(f"   Test message: '{test_message}'")
    
    try:
        response = await agent_service.process_message(
            message=test_message,
            lead_profile=lead_profile,
            conversation_context=context,
            conversation_history=history,
            channel="sms",
            fub_person_id=PERSON_ID,
            user_id=user_id,
            organization_id=organization_id,
        )
        
        if response and response.response_text:
            print(f"\n   [OK] AI RESPONSE GENERATED!")
            print(f"   Response: {response.response_text[:200]}...")
            print(f"   Intent: {response.detected_intent}")
            print(f"   Handoff: {response.should_handoff}")
        else:
            print(f"\n   [FAIL] No response generated")
            print(f"   Response object: {response}")
    except Exception as e:
        print(f"\n   [FAIL] Error processing message: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_ai_processing())
