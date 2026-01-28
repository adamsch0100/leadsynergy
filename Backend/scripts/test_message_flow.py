"""
Test CONSECUTIVE Playwright message operations to reproduce session stability issues.

This simulates what happens when multiple webhooks arrive in quick succession:
1. First message - read it via Playwright
2. Second message (few seconds later) - should also read successfully
3. Third message - should also work

The goal is to reproduce the issue where first operation works but subsequent ones fail.

Usage:
    python scripts/test_message_flow.py --person-id 2099 --count 3 --delay 5

Options:
    --person-id   FUB person ID to test with (default: 2099)
    --count       Number of consecutive reads to attempt (default: 3)
    --delay       Seconds between operations (default: 5)
    --headless    Run browser in headless mode (default: visible)
"""
import asyncio
import os
import sys
import time
import logging
import argparse

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,  # DEBUG to see all Playwright activity
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress noisy loggers
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

# Add Backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestResult:
    """Container for test results."""
    def __init__(self, iteration: int):
        self.iteration = iteration
        self.success = False
        self.message = None
        self.error = None
        self.timing = {}
        self.screenshot_path = None

    def __str__(self):
        status = "SUCCESS" if self.success else "FAILED"
        total_time = self.timing.get('total', 0)
        return f"[Test {self.iteration}] {status} ({total_time:.2f}s)"


async def run_single_read(service, agent_id: str, person_id: int, credentials: dict, iteration: int) -> TestResult:
    """Run a single message read and capture timing."""
    result = TestResult(iteration)

    print(f"\n{'='*60}")
    print(f"[Test {iteration}] Reading messages for person {person_id}...")
    print(f"{'='*60}")

    start_time = time.time()

    try:
        # Time the read operation
        read_start = time.time()
        read_result = await service.read_latest_message(
            agent_id=agent_id,
            person_id=person_id,
            credentials=credentials,
        )
        read_end = time.time()

        result.timing['read'] = read_end - read_start
        result.timing['total'] = time.time() - start_time

        if read_result.get('success'):
            result.success = True
            result.message = read_result.get('message', 'N/A')
            print(f"  [OK] Message read successfully!")
            print(f"  Message: {result.message[:80]}{'...' if len(str(result.message)) > 80 else ''}")
        else:
            result.success = False
            result.error = read_result.get('error', 'Unknown error')
            print(f"  [FAIL] {result.error}")
            result.screenshot_path = read_result.get('debug_screenshot')

    except asyncio.TimeoutError:
        result.timing['total'] = time.time() - start_time
        result.error = "Operation timed out"
        print(f"  [FAIL] TIMEOUT after {result.timing['total']:.1f}s")

    except Exception as e:
        result.timing['total'] = time.time() - start_time
        result.error = str(e)
        print(f"  [FAIL] Exception: {e}")
        import traceback
        traceback.print_exc()

    # Print timing breakdown
    print(f"\n  Timing:")
    for step, duration in result.timing.items():
        print(f"    - {step}: {duration:.2f}s")

    return result


async def test_consecutive_operations(person_id: int, count: int, delay: float):
    """Test multiple consecutive Playwright operations."""

    print("=" * 70)
    print("CONSECUTIVE PLAYWRIGHT OPERATIONS TEST")
    print("=" * 70)
    print(f"  Person ID: {person_id}")
    print(f"  Operations: {count}")
    print(f"  Delay between: {delay}s")
    print(f"  Headless: {os.getenv('PLAYWRIGHT_HEADLESS', 'false')}")
    print("=" * 70)

    # Import after path setup
    from app.database.supabase_client import SupabaseClientSingleton
    from app.ai_agent.settings_service import get_fub_browser_credentials
    from app.webhook.ai_webhook_handlers import resolve_organization_for_person, resolve_user_for_person
    from app.messaging.playwright_sms_service import PlaywrightSMSService

    supabase = SupabaseClientSingleton.get_instance()

    # Resolve organization and user
    print("\n1. Resolving organization and user...")
    organization_id = await resolve_organization_for_person(person_id)
    user_id = await resolve_user_for_person(person_id, organization_id)

    if not organization_id or not user_id:
        print("   [FAIL] Could not resolve org/user")
        return

    print(f"   Organization: {organization_id}")
    print(f"   User: {user_id}")

    # Get credentials
    print("\n2. Getting FUB credentials...")
    credentials = await get_fub_browser_credentials(
        supabase_client=supabase,
        user_id=user_id,
        organization_id=organization_id,
    )

    if not credentials:
        print("   [FAIL] No FUB credentials found!")
        return

    print(f"   [OK] Got credentials for: {credentials.get('email', 'unknown')}")

    # Initialize service
    print("\n3. Initializing Playwright service...")
    service = PlaywrightSMSService()
    agent_id = credentials.get("agent_id", user_id or "default")

    # Run consecutive operations
    results = []

    try:
        for i in range(1, count + 1):
            result = await run_single_read(service, agent_id, person_id, credentials, i)
            results.append(result)

            # If not the last iteration, wait before next
            if i < count:
                print(f"\n--- Waiting {delay}s before next operation ---")
                await asyncio.sleep(delay)

    finally:
        print("\n4. Cleaning up...")
        await service.shutdown()

    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    successes = sum(1 for r in results if r.success)
    failures = sum(1 for r in results if not r.success)

    print(f"  Total: {len(results)}")
    print(f"  Successes: {successes}")
    print(f"  Failures: {failures}")
    print()

    for result in results:
        status = "OK" if result.success else "FAIL"
        print(f"  [{status}] Test {result.iteration}: {result.timing.get('total', 0):.2f}s", end="")
        if result.error:
            print(f" - {result.error[:50]}")
        else:
            print()

    print()

    if failures > 0:
        print("RESULT: FAILED - Some operations did not complete successfully")
        print("\nThis reproduces the production issue!")
        print("Look at the logs above to see where it got stuck.")
        if any(r.screenshot_path for r in results):
            print("\nScreenshots captured:")
            for r in results:
                if r.screenshot_path:
                    print(f"  - Test {r.iteration}: {r.screenshot_path}")
    else:
        print("RESULT: SUCCESS - All operations completed!")
        print("\nIf production is failing but local works, the issue may be:")
        print("  - Railway container resource limits")
        print("  - Network latency to FUB")
        print("  - Saved session cookies are corrupted in Supabase")

    print("\n" + "=" * 70)

    return results


async def test_send_after_read(person_id: int, delay: float):
    """Test read followed by send - the actual webhook flow."""

    print("=" * 70)
    print("READ THEN SEND TEST (SIMULATES WEBHOOK FLOW)")
    print("=" * 70)
    print(f"  Person ID: {person_id}")
    print(f"  Delay between: {delay}s")
    print("=" * 70)

    # Import after path setup
    from app.database.supabase_client import SupabaseClientSingleton
    from app.ai_agent.settings_service import get_fub_browser_credentials
    from app.webhook.ai_webhook_handlers import resolve_organization_for_person, resolve_user_for_person
    from app.messaging.playwright_sms_service import PlaywrightSMSService

    supabase = SupabaseClientSingleton.get_instance()

    # Resolve organization and user
    print("\n1. Resolving organization and user...")
    organization_id = await resolve_organization_for_person(person_id)
    user_id = await resolve_user_for_person(person_id, organization_id)

    if not organization_id or not user_id:
        print("   [FAIL] Could not resolve org/user")
        return

    # Get credentials
    print("\n2. Getting FUB credentials...")
    credentials = await get_fub_browser_credentials(
        supabase_client=supabase,
        user_id=user_id,
        organization_id=organization_id,
    )

    if not credentials:
        print("   [FAIL] No FUB credentials found!")
        return

    print(f"   [OK] Got credentials for: {credentials.get('email', 'unknown')}")

    # Initialize service
    print("\n3. Initializing Playwright service...")
    service = PlaywrightSMSService()
    agent_id = credentials.get("agent_id", user_id or "default")

    try:
        # Step 1: Read message
        print(f"\n{'='*60}")
        print("[Step 1] Reading latest message...")
        print(f"{'='*60}")

        start = time.time()
        read_result = await service.read_latest_message(
            agent_id=agent_id,
            person_id=person_id,
            credentials=credentials,
        )
        read_time = time.time() - start

        if read_result.get('success'):
            print(f"  [OK] Read completed in {read_time:.2f}s")
            print(f"  Message: {read_result.get('message', 'N/A')[:80]}")
        else:
            print(f"  [FAIL] Read failed: {read_result.get('error')}")
            return

        # Wait like production would
        print(f"\n--- Simulating AI processing ({delay}s) ---")
        await asyncio.sleep(delay)

        # Step 2: Send response
        print(f"\n{'='*60}")
        print("[Step 2] Sending response message...")
        print(f"{'='*60}")

        test_message = f"[LOCAL TEST] Reply at {time.strftime('%H:%M:%S')}"

        start = time.time()
        send_result = await service.send_sms(
            agent_id=agent_id,
            person_id=person_id,
            message=test_message,
            credentials=credentials,
        )
        send_time = time.time() - start

        if send_result.get('success'):
            print(f"  [OK] Send completed in {send_time:.2f}s")
        else:
            print(f"  [FAIL] Send failed: {send_result.get('error')}")
            return

        # Wait then try to read another message
        print(f"\n--- Waiting {delay}s before second read ---")
        await asyncio.sleep(delay)

        # Step 3: Read again (this is where production usually fails)
        print(f"\n{'='*60}")
        print("[Step 3] Reading again (second operation)...")
        print(f"{'='*60}")

        start = time.time()
        read_result2 = await service.read_latest_message(
            agent_id=agent_id,
            person_id=person_id,
            credentials=credentials,
        )
        read_time2 = time.time() - start

        if read_result2.get('success'):
            print(f"  [OK] Second read completed in {read_time2:.2f}s")
            print(f"  Message: {read_result2.get('message', 'N/A')[:80]}")
        else:
            print(f"  [FAIL] Second read failed: {read_result2.get('error')}")
            print("\n  ^^^ THIS IS THE PRODUCTION BUG ^^^")

    finally:
        print("\n4. Cleaning up...")
        await service.shutdown()

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test consecutive Playwright operations')
    parser.add_argument('--person-id', type=int, default=2099, help='FUB person ID to test with')
    parser.add_argument('--count', type=int, default=3, help='Number of consecutive reads')
    parser.add_argument('--delay', type=float, default=5, help='Seconds between operations')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--mode', choices=['read', 'flow'], default='read',
                        help='read=consecutive reads, flow=read+send+read')

    args = parser.parse_args()

    # Set headless mode
    if args.headless:
        os.environ['PLAYWRIGHT_HEADLESS'] = 'true'
    else:
        os.environ['PLAYWRIGHT_HEADLESS'] = 'false'

    print(f"\nStarting test with visible browser (set --headless to hide)...")
    print(f"Watch the browser to see exactly where it gets stuck!\n")

    if args.mode == 'flow':
        asyncio.run(test_send_after_read(args.person_id, args.delay))
    else:
        asyncio.run(test_consecutive_operations(args.person_id, args.count, args.delay))
