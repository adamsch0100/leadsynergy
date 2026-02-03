"""
Test email verification link extraction locally.
This helps debug why FUB verification emails aren't being found.
"""
import os
import sys
import logging

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Setup verbose logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Add Backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_email_search():
    """Test email search without needing the full Playwright flow."""
    print("=" * 70)
    print("EMAIL VERIFICATION LINK TEST")
    print("=" * 70)

    # Get Gmail credentials
    gmail_email = os.getenv("GMAIL_EMAIL") or "adam@saahomes.com"
    gmail_password = os.getenv("GMAIL_APP_PASSWORD") or "jjuh jarv rlad sqye"

    print(f"\n1. Gmail credentials:")
    print(f"   Email: {gmail_email}")
    print(f"   Password: {'*' * 8}...{gmail_password[-4:] if gmail_password else 'NOT SET'}")

    if not gmail_email or not gmail_password:
        print("\n   [FAIL] Gmail credentials not set!")
        return

    print(f"\n2. Testing IMAP connection...")

    from app.utils.email_2fa_helper import Email2FAHelper

    helper = Email2FAHelper(
        email_address=gmail_email,
        app_password=gmail_password
    )

    try:
        with helper:
            print("   [OK] IMAP connection successful!")

            print(f"\n3. Searching for FUB verification emails...")
            print(f"   Criteria: sender contains 'followupboss', max age 300s")
            print(f"   Looking for links containing 'followupboss.com'")

            # Try to find the verification link
            link = helper.get_verification_link(
                sender_contains="followupboss",
                subject_contains=None,  # No subject filter
                link_contains="followupboss.com",
                max_age_seconds=300,  # 5 minutes
                max_retries=1,  # Only try once for testing
                retry_delay=0
            )

            if link:
                print(f"\n   [OK] FOUND VERIFICATION LINK!")
                print(f"   Link: {link}")
            else:
                print(f"\n   [FAIL] No verification link found")
                print(f"\n4. Let's check what emails ARE in the inbox...")

                # Do a broader search to see what's there
                test_broader_search(helper)

    except Exception as e:
        print(f"\n   [FAIL] Error: {e}")
        import traceback
        traceback.print_exc()


def test_broader_search(helper):
    """Do a broader email search to see what's in the inbox."""
    import email
    from datetime import datetime, timedelta

    try:
        helper._connection.select("INBOX")

        # Search for ALL recent emails (last 10 minutes)
        since_date = (datetime.now() - timedelta(seconds=600)).strftime("%d-%b-%Y")
        search_criteria = f'(SINCE "{since_date}")'

        status, message_ids = helper._connection.search(None, search_criteria)

        if status != "OK" or not message_ids[0]:
            print("   No recent emails found at all")
            return

        ids = message_ids[0].split()
        ids.reverse()

        print(f"\n   Found {len(ids)} emails in last 10 minutes:")
        print("-" * 60)

        for i, msg_id in enumerate(ids[:10]):
            try:
                status, msg_data = helper._connection.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                from_header = msg.get("From", "")
                subject = helper._decode_header(msg.get("Subject", ""))
                date_str = msg.get("Date", "")

                print(f"\n   [{i+1}] From: {from_header[:50]}")
                print(f"       Subject: {subject[:50]}")
                print(f"       Date: {date_str[:30]}")

                # Check if this looks like a FUB email
                if "followupboss" in from_header.lower():
                    print(f"       *** THIS IS A FUB EMAIL! ***")

                    # Extract and show links
                    body = helper._get_email_body_html(msg)
                    print(f"       Body length: {len(body)} chars")

                    # Find all links
                    import re
                    links = re.findall(r'href=["\']([^"\']+)["\']', body, re.IGNORECASE)
                    fub_links = [l for l in links if 'followupboss' in l.lower()]

                    print(f"       Total links: {len(links)}")
                    print(f"       FUB links: {len(fub_links)}")

                    for link in fub_links[:5]:
                        print(f"       -> {link[:80]}")

            except Exception as e:
                print(f"   Error parsing email: {e}")
                continue

        print("-" * 60)

    except Exception as e:
        print(f"   Error in broader search: {e}")


if __name__ == "__main__":
    test_email_search()
