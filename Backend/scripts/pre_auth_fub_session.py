"""
Pre-authenticate FUB session from a trusted location (your local machine).

The Problem:
- Railway's datacenter IP triggers FUB's "new location" security check EVERY time
- This requires email verification on each login attempt
- This is unsustainable and will get the account rate-limited

The Solution:
- Run this script locally (from your home/office IP that FUB trusts)
- It logs into FUB WITHOUT triggering security checks
- Saves the session cookies to Supabase
- Railway then uses those pre-authenticated cookies instead of trying to login fresh

Usage:
    python scripts/pre_auth_fub_session.py

After running, the Railway deployment will use these cookies and avoid the verification flow.
"""
import asyncio
import os
import sys
import logging

from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress noisy loggers
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# Add Backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def pre_authenticate():
    """Login to FUB from trusted location and save cookies for Railway."""

    print("=" * 70)
    print("FUB PRE-AUTHENTICATION")
    print("=" * 70)
    print()
    print("This script logs into FUB from your local machine (trusted IP)")
    print("and saves the session cookies for Railway to use.")
    print()
    print("This avoids Railway triggering FUB's 'new location' security check.")
    print("=" * 70)

    # Import after path setup
    from app.database.supabase_client import SupabaseClientSingleton
    from app.ai_agent.settings_service import get_fub_browser_credentials
    from app.messaging.playwright_sms_service import PlaywrightSMSService

    supabase = SupabaseClientSingleton.get_instance()

    # Get a test user/organization to get credentials
    # You may need to adjust this based on your setup
    print("\n1. Getting FUB credentials from database...")

    # Try to get credentials for a known user
    # First, let's get any user with FUB browser credentials
    try:
        result = supabase.from_("ai_agent_settings").select("*").limit(1).execute()
        if result.data and len(result.data) > 0:
            settings = result.data[0]
            user_id = settings.get('user_id')
            organization_id = settings.get('organization_id')
            print(f"   Found settings for user_id={user_id}, org_id={organization_id}")
        else:
            print("   No AI agent settings found!")
            return
    except Exception as e:
        print(f"   Error getting settings: {e}")
        return

    credentials = await get_fub_browser_credentials(
        supabase_client=supabase,
        user_id=user_id,
        organization_id=organization_id
    )

    if not credentials:
        print("   [FAIL] No FUB credentials found!")
        print("   Make sure FUB browser credentials are configured in ai_agent_settings")
        return

    print(f"   [OK] Found credentials for: {credentials.get('email', 'unknown')}")
    agent_id = credentials.get('agent_id', user_id or 'default')
    print(f"   Agent ID: {agent_id}")

    # Initialize Playwright service
    print("\n2. Initializing Playwright (visible browser)...")

    # Force visible browser for local authentication
    os.environ['PLAYWRIGHT_HEADLESS'] = 'false'

    service = PlaywrightSMSService()
    await service.initialize()

    print("   [OK] Browser initialized")

    # Create session and login
    print("\n3. Logging into FUB...")
    print("   (A browser window will open - complete any 2FA if needed)")
    print()

    try:
        session = await service.get_or_create_session(agent_id, credentials)
        print("   [OK] Login successful!")

        # Test the session
        print("\n4. Testing session validity...")
        is_valid = await session.is_valid(skip_if_warm=False)

        if is_valid:
            print("   [OK] Session is valid!")

            # Save cookies explicitly
            print("\n5. Saving session cookies to Supabase...")
            cookies = await session.context.cookies()
            await service.session_store.save_cookies(agent_id, cookies)
            print(f"   [OK] Saved {len(cookies)} cookies for agent {agent_id}")

            print("\n" + "=" * 70)
            print("SUCCESS!")
            print("=" * 70)
            print()
            print("The FUB session cookies have been saved to Supabase.")
            print("Railway will now use these pre-authenticated cookies.")
            print()
            print("Note: Cookies may expire after some time (usually 7-30 days).")
            print("Re-run this script when Railway starts getting 'new location' errors again.")
            print()
        else:
            print("   [FAIL] Session validation failed!")

    except Exception as e:
        print(f"   [FAIL] Login failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("\n6. Cleaning up...")
        await service.shutdown()
        print("   Done!")


if __name__ == "__main__":
    asyncio.run(pre_authenticate())
