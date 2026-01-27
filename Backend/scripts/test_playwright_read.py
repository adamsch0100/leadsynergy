"""
Test Playwright message reading functionality locally.
This tests the ability to read SMS content from FUB web UI.
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
required_vars = ['SUPABASE_URL', 'SUPABASE_KEY', 'FUB_API_KEY']
missing = [v for v in required_vars if not os.getenv(v)]
if missing:
    print(f"ERROR: Missing environment variables: {missing}")
    sys.exit(1)

# Check for FUB login credentials
fub_email = os.getenv('FUB_LOGIN_EMAIL')
fub_password = os.getenv('FUB_LOGIN_PASSWORD')
if not fub_email or not fub_password:
    print("WARNING: FUB_LOGIN_EMAIL and FUB_LOGIN_PASSWORD not in env vars")
    print("Will try to fetch from database...")

print(f"  [OK] All required env vars present")


async def test_playwright_read():
    """Test the Playwright message reading flow."""
    print("=" * 70)
    print("Testing Playwright Message Reading")
    print("=" * 70)

    # Import after path setup
    from app.database.supabase_client import SupabaseClientSingleton
    from app.database.fub_api_client import FUBApiClient

    supabase = SupabaseClientSingleton.get_instance()
    fub_client = FUBApiClient()

    # Use a real FUB person ID for testing - change this to a lead with messages
    PERSON_ID = 2099  # Change this to a test lead with messages

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

    print(f"\n3. Getting FUB browser credentials...")
    from app.ai_agent.settings_service import get_fub_browser_credentials
    credentials = await get_fub_browser_credentials(
        supabase_client=supabase,
        user_id=user_id,
        organization_id=organization_id,
    )

    if not credentials:
        print("   [FAIL] No FUB credentials found!")
        print("   Make sure FUB_LOGIN_EMAIL and FUB_LOGIN_PASSWORD are set in .env or database")
        return

    print(f"   [OK] Got credentials for: {credentials.get('email', 'unknown')}")
    print(f"   Login type: {credentials.get('type', 'email')}")

    print(f"\n4. Testing FUB API text messages (expect 'Body is hidden')...")
    try:
        # Try to get messages via API - should return hidden content
        import requests
        import base64

        api_key = os.getenv('FUB_API_KEY')
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {base64.b64encode(f"{api_key}:".encode()).decode()}',
        }

        response = requests.get(
            f"https://api.followupboss.com/v1/textMessages?personId={PERSON_ID}&limit=5",
            headers=headers
        )

        if response.status_code == 200:
            data = response.json()
            messages = data.get('textmessages', [])
            print(f"   Found {len(messages)} messages via API")
            for i, msg in enumerate(messages[:3]):
                content = msg.get('message', 'N/A')
                is_incoming = msg.get('isIncoming', False)
                direction = 'INBOUND' if is_incoming else 'OUTBOUND'
                print(f"   [{direction}] {content[:60]}{'...' if len(content) > 60 else ''}")
        else:
            print(f"   API returned status {response.status_code}")
    except Exception as e:
        print(f"   [WARN] API test failed: {e}")

    print(f"\n5. Initializing Playwright SMS Service...")
    from app.messaging.playwright_sms_service import PlaywrightSMSService
    service = PlaywrightSMSService()

    print(f"\n6. Reading latest message via Playwright (headless={os.getenv('PLAYWRIGHT_HEADLESS', 'true')})...")
    print("   This will open a browser, login to FUB, and read the messages...")
    print("   Set PLAYWRIGHT_HEADLESS=false to watch the browser")

    agent_id = credentials.get("agent_id", user_id or "default")

    try:
        result = await service.read_latest_message(
            agent_id=agent_id,
            person_id=PERSON_ID,
            credentials=credentials,
        )

        if result.get('success'):
            print(f"\n   [OK] SUCCESSFULLY READ MESSAGE VIA PLAYWRIGHT!")
            print(f"   Message: {result.get('message', 'N/A')}")
            print(f"   Person ID: {result.get('person_id')}")
        else:
            print(f"\n   [FAIL] Could not read message: {result.get('error')}")
            if result.get('debug_screenshot'):
                print(f"   Debug screenshot: {result.get('debug_screenshot')}")
    except Exception as e:
        print(f"\n   [FAIL] Playwright read failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"\n7. Cleaning up...")
        await service.shutdown()

    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)


async def test_full_webhook_flow():
    """Test the full webhook flow with Playwright fallback."""
    print("=" * 70)
    print("Testing Full Webhook Flow (simulated)")
    print("=" * 70)

    from app.database.supabase_client import SupabaseClientSingleton
    from app.database.fub_api_client import FUBApiClient

    supabase = SupabaseClientSingleton.get_instance()
    fub_client = FUBApiClient()

    PERSON_ID = 2099  # Change this

    print(f"\n1. Simulating webhook with hidden content...")

    # Simulate what happens when webhook fires with hidden content
    simulated_message = "* Body is hidden for privacy reasons *"
    print(f"   API returned: {simulated_message}")

    # Check if it's hidden
    if "Body is hidden" in simulated_message:
        print(f"   Detected hidden content! Would use Playwright to read actual message...")

    print(f"\n2. Would proceed with AI processing using actual message content...")

    print("\n" + "=" * 70)
    print("Simulated Flow Complete")
    print("=" * 70)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Test Playwright message reading')
    parser.add_argument('--full-flow', action='store_true', help='Test full webhook flow simulation')
    parser.add_argument('--person-id', type=int, default=2099, help='FUB person ID to test with')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    args = parser.parse_args()

    if args.headless:
        os.environ['PLAYWRIGHT_HEADLESS'] = 'true'
    else:
        # Default to non-headless for debugging
        os.environ['PLAYWRIGHT_HEADLESS'] = 'false'

    if args.full_flow:
        asyncio.run(test_full_webhook_flow())
    else:
        asyncio.run(test_playwright_read())
