"""
Debug script to see exactly what emails are in the inbox and why they might not be found.
"""
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta
import os
import sys

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def decode_header_value(header):
    """Decode email header"""
    try:
        decoded_parts = decode_header(header)
        result = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result += part.decode(encoding or "utf-8", errors="ignore")
            else:
                result += part
        return result
    except:
        return header

def main():
    # Get credentials
    gmail_email = os.getenv("GMAIL_EMAIL")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    if not gmail_email or not gmail_password:
        # Try from database
        from app.database.supabase_client import SupabaseClientSingleton
        supabase = SupabaseClientSingleton.get_instance()
        result = supabase.table('system_settings').select('gmail_email, gmail_app_password').limit(1).execute()
        if result.data:
            gmail_email = result.data[0].get('gmail_email')
            gmail_password = result.data[0].get('gmail_app_password')

    print("=" * 70)
    print("EMAIL SEARCH DEBUG")
    print("=" * 70)
    print(f"\nGmail: {gmail_email}")
    print(f"Password: {'*' * 8}...{gmail_password[-4:] if gmail_password else 'NOT SET'}")

    # Connect
    print("\n1. Connecting to IMAP...")
    conn = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    conn.login(gmail_email, gmail_password.replace(" ", ""))
    print("   Connected!")

    conn.select("INBOX")

    # Search for ALL FUB emails in last 10 minutes
    since_date = (datetime.now() - timedelta(minutes=10)).strftime("%d-%b-%Y")

    print("\n2. Searching for FUB emails...")
    print(f"   Since: {since_date}")

    # First, get ALL emails and filter manually
    status, message_ids = conn.search(None, f'(SINCE "{since_date}")')
    all_ids = message_ids[0].split() if message_ids[0] else []
    print(f"   Total emails since {since_date}: {len(all_ids)}")

    # Now search UNREAD
    status, message_ids = conn.search(None, f'(SINCE "{since_date}" UNSEEN)')
    unread_ids = message_ids[0].split() if message_ids[0] else []
    print(f"   UNREAD emails: {len(unread_ids)}")

    # Check each email
    print("\n3. Checking each email for FUB...")
    print("-" * 70)

    fub_emails = []

    # Check most recent first
    all_ids.reverse()

    for i, msg_id in enumerate(all_ids[:30]):  # Check last 30
        status, msg_data = conn.fetch(msg_id, "(RFC822 FLAGS)")

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        # Get flags (READ/UNREAD status)
        flags_data = msg_data[0][0].decode() if isinstance(msg_data[0][0], bytes) else str(msg_data[0][0])
        is_read = "\\Seen" in flags_data

        from_header = msg.get("From", "")
        subject = decode_header_value(msg.get("Subject", ""))
        date_str = msg.get("Date", "")

        # Check if FUB
        is_fub = "followupboss" in from_header.lower()

        # Calculate age
        try:
            msg_date = email.utils.parsedate_to_datetime(date_str)
            now = datetime.now(msg_date.tzinfo) if msg_date.tzinfo else datetime.now()
            age_seconds = (now - msg_date).total_seconds()
        except:
            age_seconds = -1

        status_str = "READ" if is_read else "UNREAD"

        if is_fub:
            print(f"\n   [{i+1}] *** FUB EMAIL ***")
            print(f"       From: {from_header[:60]}")
            print(f"       Subject: {subject[:50]}")
            print(f"       Date: {date_str}")
            print(f"       Age: {age_seconds:.0f} seconds ({age_seconds/60:.1f} minutes)")
            print(f"       Status: {status_str}")
            print(f"       Msg ID: {msg_id}")

            # Check for verification link
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/html":
                        try:
                            payload = part.get_payload(decode=True)
                            charset = part.get_content_charset() or "utf-8"
                            body = payload.decode(charset, errors="ignore")
                            break
                        except:
                            pass
            else:
                try:
                    payload = msg.get_payload(decode=True)
                    charset = msg.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="ignore")
                except:
                    pass

            # Find FUB links
            import re
            links = re.findall(r'href=["\']([^"\']*followupboss[^"\']*)["\']', body, re.IGNORECASE)
            links += re.findall(r'(https?://[^\s<>"\']*followupboss[^\s<>"\']*)', body, re.IGNORECASE)

            verify_links = [l for l in links if 'validate' in l.lower() or 'verify' in l.lower() or 'locationchange' in l.lower()]

            print(f"       Verification links: {len(verify_links)}")
            for link in verify_links[:3]:
                print(f"         -> {link[:80]}...")

            fub_emails.append({
                'id': msg_id,
                'age': age_seconds,
                'is_read': is_read,
                'has_link': len(verify_links) > 0
            })
        else:
            # Just show first few non-FUB for context
            if i < 5:
                print(f"\n   [{i+1}] From: {from_header[:40]}... | {status_str} | {age_seconds:.0f}s old")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nFUB emails found: {len(fub_emails)}")

    if fub_emails:
        fresh = [e for e in fub_emails if e['age'] < 300 and e['age'] > 0]
        unread_fub = [e for e in fub_emails if not e['is_read']]
        with_link = [e for e in fub_emails if e['has_link']]

        print(f"  - Fresh (< 5 min old): {len(fresh)}")
        print(f"  - UNREAD: {len(unread_fub)}")
        print(f"  - With verification link: {len(with_link)}")

        if fresh and with_link:
            print("\n  ✓ Should be able to find and use a verification link!")
        elif not fresh:
            print("\n  ✗ No fresh FUB emails - all are too old (> 5 min)")
            print("    The new verification email hasn't arrived yet, or FUB isn't sending one")
        elif not with_link:
            print("\n  ✗ FUB emails exist but none have verification links")
    else:
        print("\n  ✗ No FUB emails found at all in the last 10 minutes")

    conn.logout()

if __name__ == "__main__":
    main()
