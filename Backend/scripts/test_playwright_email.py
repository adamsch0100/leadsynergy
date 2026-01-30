#!/usr/bin/env python3
"""
Test Playwright email sending via FUB web UI.

Three modes:
  --discover    Navigate to lead page, screenshot email UI, enumerate selectors
  --dry-run     Full email compose flow but DON'T click Send
  --send        Actually send a test email

Usage:
    python scripts/test_playwright_email.py --discover
    python scripts/test_playwright_email.py --dry-run
    python scripts/test_playwright_email.py --send
    python scripts/test_playwright_email.py --discover --person-id 2099
    python scripts/test_playwright_email.py --discover --headless
"""
import asyncio
import os
import sys
import logging
import argparse

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Add Backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Screenshot output directory
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


async def get_credentials_and_session(person_id: int, headless: bool = False):
    """Get FUB credentials and initialize a browser session."""
    from app.database.supabase_client import SupabaseClientSingleton
    from app.database.fub_api_client import FUBApiClient

    supabase = SupabaseClientSingleton.get_instance()
    fub_client = FUBApiClient()

    print(f"\n1. Getting person data for ID {person_id}...")
    person_data = fub_client.get_person(person_id)
    if not person_data:
        print("   [FAIL] Person not found")
        return None, None, None
    print(f"   [OK] {person_data.get('firstName')} {person_data.get('lastName')}")

    print(f"\n2. Resolving organization...")
    from app.webhook.ai_webhook_handlers import resolve_organization_for_person, resolve_user_for_person
    organization_id = await resolve_organization_for_person(person_id)
    user_id = await resolve_user_for_person(person_id, organization_id)
    print(f"   Organization: {organization_id}")
    print(f"   User: {user_id}")

    print(f"\n3. Getting FUB browser credentials...")
    from app.ai_agent.settings_service import get_fub_browser_credentials
    credentials = await get_fub_browser_credentials(
        supabase_client=supabase,
        user_id=user_id,
        organization_id=organization_id,
    )

    if not credentials:
        print("   [FAIL] No credentials found. Set FUB_LOGIN_EMAIL and FUB_LOGIN_PASSWORD in .env")
        return None, None, None
    print(f"   [OK] Login type: {credentials.get('type')}, email: {credentials.get('email')}")

    print(f"\n4. Initializing Playwright browser session...")
    from app.messaging.fub_browser_session import FUBBrowserSession
    session = FUBBrowserSession(headless=headless)
    await session.initialize()

    print(f"\n5. Logging in to FUB...")
    login_result = await session.login(
        email=credentials['email'],
        password=credentials['password'],
        login_type=credentials.get('type', 'email'),
    )
    if not login_result.get('success'):
        print(f"   [FAIL] Login failed: {login_result.get('error')}")
        await session.close()
        return None, None, None
    print(f"   [OK] Logged in successfully")

    return session, person_data, credentials


async def discover_email_ui(person_id: int, headless: bool = False):
    """
    Navigate to a lead's page and discover the email compose UI elements.
    Takes screenshots at each step and enumerates all available selectors.
    """
    print("=" * 70)
    print("  PLAYWRIGHT EMAIL DISCOVERY TEST")
    print("=" * 70)

    session, person_data, credentials = await get_credentials_and_session(person_id, headless)
    if not session:
        return

    try:
        page = session.page
        person_url = f"https://app.followupboss.com/2/people/view/{person_id}"

        print(f"\n6. Navigating to lead page: {person_url}")
        await page.goto(person_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # Screenshot 1: Full lead page
        ss1 = os.path.join(SCREENSHOT_DIR, f"email_discover_1_lead_page_{person_id}.png")
        await page.screenshot(path=ss1)
        print(f"   [SCREENSHOT] Lead page: {ss1}")

        # Enumerate all tab-like elements
        print(f"\n7. Enumerating tab elements...")
        tabs = await page.evaluate("""() => {
            const results = [];
            // Check for tab-like elements
            const selectors = [
                '[role="tab"]',
                '[class*="BoxTabPadding"]',
                '[class*="Tab"]',
                'div[class*="tab"]',
                'button[class*="tab"]',
            ];
            for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                for (const el of els) {
                    results.push({
                        selector: sel,
                        text: el.textContent.trim().substring(0, 50),
                        tagName: el.tagName,
                        className: (el.className || '').toString().substring(0, 100),
                        visible: el.offsetParent !== null,
                    });
                }
            }
            // Also look for elements with "Email" text
            const allEls = document.querySelectorAll('div, button, a, span');
            for (const el of allEls) {
                const text = el.textContent.trim();
                if (text === 'Email' && el.offsetParent !== null) {
                    results.push({
                        selector: 'text=Email',
                        text: text,
                        tagName: el.tagName,
                        className: (el.className || '').toString().substring(0, 100),
                        visible: true,
                    });
                }
            }
            return results;
        }""")

        if tabs:
            print(f"   Found {len(tabs)} tab-like elements:")
            for t in tabs:
                vis = "VISIBLE" if t['visible'] else "hidden"
                print(f"     [{vis}] <{t['tagName']}> class='{t['className'][:60]}' text='{t['text']}'")
        else:
            print("   No tab elements found!")

        # Try to click Email tab
        print(f"\n8. Attempting to click Email tab...")
        email_tab_selectors = [
            'div:has(.BaseIcon-email):has-text("Email")',
            'div:has(.BaseIcon-envelope):has-text("Email")',
            '.BaseIcon-email',
            '.BaseIcon-envelope',
            '[class*="BoxTabPadding"]:has-text("Email")',
            'button:has-text("Email")',
            'a:has-text("Email")',
            '[role="tab"]:has-text("Email")',
        ]

        email_tab_clicked = False
        for sel in email_tab_selectors:
            try:
                el = await page.wait_for_selector(sel, timeout=2000)
                if el:
                    await el.click()
                    email_tab_clicked = True
                    print(f"   [OK] Clicked via: {sel}")
                    break
            except Exception:
                continue

        if not email_tab_clicked:
            # JS fallback
            print("   CSS selectors failed, trying JavaScript fallback...")
            js_clicked = await page.evaluate("""() => {
                const allEls = document.querySelectorAll('div, button, a, span');
                for (const el of allEls) {
                    if (el.textContent.trim() === 'Email' && el.offsetParent !== null) {
                        el.click();
                        return el.tagName + '.' + (el.className || '').toString().substring(0, 50);
                    }
                }
                return null;
            }""")
            if js_clicked:
                email_tab_clicked = True
                print(f"   [OK] Clicked via JS: {js_clicked}")
            else:
                print("   [FAIL] Could not find Email tab!")

        await asyncio.sleep(2)

        # Screenshot 2: After clicking Email tab
        ss2 = os.path.join(SCREENSHOT_DIR, f"email_discover_2_email_tab_{person_id}.png")
        await page.screenshot(path=ss2)
        print(f"   [SCREENSHOT] After Email tab click: {ss2}")

        if email_tab_clicked:
            # Enumerate compose fields
            print(f"\n9. Enumerating email compose fields...")
            fields = await page.evaluate("""() => {
                const results = [];
                // Subject inputs
                const inputs = document.querySelectorAll('input');
                for (const inp of inputs) {
                    if (inp.offsetParent !== null) {
                        results.push({
                            type: 'input',
                            tagName: 'INPUT',
                            inputType: inp.type,
                            placeholder: inp.placeholder || '',
                            name: inp.name || '',
                            className: (inp.className || '').toString().substring(0, 100),
                            visible: true,
                        });
                    }
                }
                // Textareas
                const textareas = document.querySelectorAll('textarea');
                for (const ta of textareas) {
                    if (ta.offsetParent !== null) {
                        results.push({
                            type: 'textarea',
                            tagName: 'TEXTAREA',
                            placeholder: ta.placeholder || '',
                            name: ta.name || '',
                            className: (ta.className || '').toString().substring(0, 100),
                            visible: true,
                        });
                    }
                }
                // Contenteditable divs
                const editables = document.querySelectorAll('[contenteditable="true"]');
                for (const ed of editables) {
                    if (ed.offsetParent !== null) {
                        results.push({
                            type: 'contenteditable',
                            tagName: ed.tagName,
                            role: ed.getAttribute('role') || '',
                            className: (ed.className || '').toString().substring(0, 100),
                            visible: true,
                        });
                    }
                }
                // Buttons with "Send" text
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    if (btn.offsetParent !== null && btn.textContent.toLowerCase().includes('send')) {
                        results.push({
                            type: 'button',
                            tagName: 'BUTTON',
                            text: btn.textContent.trim().substring(0, 50),
                            className: (btn.className || '').toString().substring(0, 100),
                            visible: true,
                        });
                    }
                }
                return results;
            }""")

            if fields:
                print(f"   Found {len(fields)} compose UI elements:")
                for f in fields:
                    if f['type'] == 'input':
                        print(f"     [INPUT] placeholder='{f['placeholder']}' name='{f['name']}' class='{f['className'][:50]}'")
                    elif f['type'] == 'textarea':
                        print(f"     [TEXTAREA] placeholder='{f['placeholder']}' name='{f['name']}' class='{f['className'][:50]}'")
                    elif f['type'] == 'contenteditable':
                        print(f"     [CONTENTEDITABLE] <{f['tagName']}> role='{f['role']}' class='{f['className'][:50]}'")
                    elif f['type'] == 'button':
                        print(f"     [BUTTON] text='{f['text']}' class='{f['className'][:50]}'")
            else:
                print("   No compose fields found!")

        print(f"\n{'=' * 70}")
        print(f"  DISCOVERY COMPLETE")
        print(f"  Screenshots saved to: {SCREENSHOT_DIR}")
        print(f"{'=' * 70}")

    finally:
        await session.close()


async def dry_run_email(person_id: int, headless: bool = False):
    """
    Full email compose flow but DON'T click Send.
    Tests all selectors end-to-end.
    """
    print("=" * 70)
    print("  PLAYWRIGHT EMAIL DRY RUN (NO SEND)")
    print("=" * 70)

    session, person_data, credentials = await get_credentials_and_session(person_id, headless)
    if not session:
        return

    try:
        first_name = person_data.get('firstName', 'there')
        subject = f"[DRY RUN TEST] Following up - {first_name}"
        body = f"Hey {first_name}, this is a dry run test of the email compose flow. This email should NOT be sent."

        print(f"\n6. Starting email compose (DRY RUN)...")
        print(f"   Subject: {subject}")
        print(f"   Body: {body[:80]}...")
        print(f"   NOTE: Will fill all fields but NOT click Send")

        # We'll call send_email but interrupt before sending
        # Instead, manually test each step
        page = session.page
        person_url = f"https://app.followupboss.com/2/people/view/{person_id}"

        await page.goto(person_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # Click Email tab
        print(f"\n   Step 1: Click Email tab...")
        email_clicked = False
        for sel in ['button:has-text("Email")', 'a:has-text("Email")', '[role="tab"]:has-text("Email")',
                     '[class*="BoxTabPadding"]:has-text("Email")', '.BaseIcon-email', '.BaseIcon-envelope']:
            try:
                el = await page.wait_for_selector(sel, timeout=2000)
                if el:
                    await el.click()
                    email_clicked = True
                    print(f"   [OK] Email tab clicked via: {sel}")
                    break
            except Exception:
                continue

        if not email_clicked:
            js_clicked = await page.evaluate("""() => {
                const els = document.querySelectorAll('div, button, a, span');
                for (const el of els) {
                    if (el.textContent.trim() === 'Email' && el.offsetParent !== null) {
                        el.click();
                        return true;
                    }
                }
                return false;
            }""")
            if js_clicked:
                email_clicked = True
                print(f"   [OK] Email tab clicked via JS")
            else:
                print(f"   [FAIL] Could not click Email tab")
                return

        await asyncio.sleep(2)
        ss = os.path.join(SCREENSHOT_DIR, f"email_dryrun_1_tab_clicked_{person_id}.png")
        await page.screenshot(path=ss)

        # Fill subject
        print(f"\n   Step 2: Fill subject field...")
        subject_filled = False
        for sel in ['input[placeholder*="Subject"]', 'input[placeholder*="subject"]',
                     'input[name="subject"]', '[class*="subject"] input']:
            try:
                el = await page.wait_for_selector(sel, timeout=2000)
                if el:
                    await el.fill(subject)
                    subject_filled = True
                    print(f"   [OK] Subject filled via: {sel}")
                    break
            except Exception:
                continue

        if not subject_filled:
            print(f"   [FAIL] Could not find subject field")

        # Fill body
        print(f"\n   Step 3: Fill body field...")
        body_filled = False
        for sel in ['[contenteditable="true"]', 'textarea[placeholder*="Write"]',
                     'textarea[placeholder*="message"]', 'textarea']:
            try:
                el = await page.wait_for_selector(sel, timeout=2000)
                if el:
                    tag = await el.evaluate('el => el.tagName.toLowerCase()')
                    if tag in ('div', 'span', 'p'):
                        await el.evaluate('el => el.textContent = ""')
                        await page.keyboard.type(body, delay=30)
                    else:
                        await el.fill(body)
                    body_filled = True
                    print(f"   [OK] Body filled via: {sel} (<{tag}>)")
                    break
            except Exception:
                continue

        if not body_filled:
            print(f"   [FAIL] Could not find body field")

        # Take final screenshot (but DON'T click Send)
        ss2 = os.path.join(SCREENSHOT_DIR, f"email_dryrun_2_filled_{person_id}.png")
        await page.screenshot(path=ss2)
        print(f"\n   [SCREENSHOT] Filled form: {ss2}")

        # Check for Send button existence
        print(f"\n   Step 4: Verify Send button exists (NOT clicking)...")
        for sel in ['button:has-text("Send Email")', 'button:has-text("Send")',
                     '[class*="sendEmail"]', '.sendEmailButton-FSSelector']:
            try:
                el = await page.wait_for_selector(sel, timeout=2000)
                if el:
                    print(f"   [OK] Send button found via: {sel}")
                    break
            except Exception:
                continue

        print(f"\n{'=' * 70}")
        print(f"  DRY RUN COMPLETE - No email was sent")
        print(f"  Screenshots saved to: {SCREENSHOT_DIR}")
        print(f"{'=' * 70}")

    finally:
        await session.close()


async def send_test_email(person_id: int, headless: bool = False):
    """
    Actually send a test email via Playwright through FUB.
    """
    print("=" * 70)
    print("  PLAYWRIGHT EMAIL SEND TEST")
    print("=" * 70)

    session, person_data, credentials = await get_credentials_and_session(person_id, headless)
    if not session:
        return

    try:
        first_name = person_data.get('firstName', 'there')
        subject = f"Quick follow up, {first_name}"
        body = f"Hey {first_name}! Just checking in to see if you had a chance to think about what we discussed. Let me know if you have any questions — happy to help!"

        print(f"\n   Subject: {subject}")
        print(f"   Body: {body}")
        print()

        confirm = input("   Are you sure you want to SEND this email? (yes/no): ")
        if confirm.lower() != 'yes':
            print("   Cancelled.")
            return

        print(f"\n6. Sending email via Playwright...")
        result = await session.send_email(
            person_id=person_id,
            subject=subject,
            body=body,
        )

        if result.get('success'):
            print(f"\n   [SUCCESS] Email sent!")
            print(f"   Result: {result}")
        else:
            print(f"\n   [FAIL] Email send failed")
            print(f"   Error: {result.get('error')}")

        print(f"\n{'=' * 70}")
        print(f"  SEND TEST COMPLETE")
        print(f"{'=' * 70}")

    finally:
        await session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Playwright email sending via FUB")
    parser.add_argument('--discover', action='store_true', help='Discover email UI selectors')
    parser.add_argument('--dry-run', action='store_true', help='Fill email form but do NOT send')
    parser.add_argument('--send', action='store_true', help='Actually send a test email')
    parser.add_argument('--person-id', type=int, default=2099, help='FUB person ID (default: 2099)')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')

    args = parser.parse_args()

    if not any([args.discover, args.dry_run, args.send]):
        parser.print_help()
        print("\nExamples:")
        print("  python scripts/test_playwright_email.py --discover")
        print("  python scripts/test_playwright_email.py --dry-run")
        print("  python scripts/test_playwright_email.py --send --person-id 2099")
        sys.exit(0)

    if args.discover:
        asyncio.run(discover_email_ui(args.person_id, args.headless))
    elif args.dry_run:
        asyncio.run(dry_run_email(args.person_id, args.headless))
    elif args.send:
        asyncio.run(send_test_email(args.person_id, args.headless))
