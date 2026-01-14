"""
Quick diagnostic script to test Gmail IMAP connection
"""
import imaplib
import os
from dotenv import load_dotenv

load_dotenv()

email = os.getenv('GMAIL_EMAIL')
app_password = os.getenv('GMAIL_APP_PASSWORD')

print("=" * 60)
print("Gmail IMAP Connection Test")
print("=" * 60)
print(f"\nEmail: {email}")
print(f"App Password: {'*' * 4} {app_password[-4:] if app_password else 'NOT SET'}")
print(f"App Password (raw length): {len(app_password) if app_password else 0} characters")

# Remove spaces from app password (Google displays with spaces for readability)
clean_password = app_password.replace(" ", "") if app_password else ""
print(f"App Password (cleaned length): {len(clean_password)} characters")

print("\n" + "=" * 60)
print("Attempting IMAP connection...")
print("=" * 60)

try:
    # Connect to Gmail IMAP
    print("\n[1] Connecting to imap.gmail.com:993...")
    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    print("    SUCCESS: Connected to server")

    # Try to login
    print(f"\n[2] Logging in as {email}...")
    imap.login(email, clean_password)
    print("    SUCCESS: Login successful!")

    # Try to select inbox
    print("\n[3] Selecting INBOX...")
    status, count = imap.select("INBOX")
    print(f"    SUCCESS: INBOX selected, {count[0].decode()} messages")

    # Search for recent emails
    print("\n[4] Searching for recent emails...")
    status, messages = imap.search(None, "ALL")
    if status == "OK":
        ids = messages[0].split()
        print(f"    SUCCESS: Found {len(ids)} total emails")

        # Show last 5 emails
        if ids:
            print("\n    Last 5 emails:")
            for msg_id in ids[-5:]:
                status, data = imap.fetch(msg_id, "(BODY[HEADER.FIELDS (FROM SUBJECT DATE)])")
                if status == "OK":
                    header = data[0][1].decode('utf-8', errors='ignore')
                    lines = header.strip().split('\r\n')
                    for line in lines:
                        if line:
                            print(f"      {line[:70]}...")
                    print()

    # Logout
    imap.logout()
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED - IMAP is working correctly!")
    print("=" * 60)

except imaplib.IMAP4.error as e:
    print(f"\n    FAILED: IMAP error - {e}")
    print("\n" + "=" * 60)
    print("TROUBLESHOOTING:")
    print("=" * 60)
    print("""
1. VERIFY IMAP IS ENABLED:
   - Go to: Gmail Settings -> See all settings -> Forwarding and POP/IMAP
   - Look for "IMAP access" section
   - Make sure it says "IMAP is enabled" (not just settings visible)
   - If disabled, enable it and click "Save Changes"

2. VERIFY/REGENERATE APP PASSWORD:
   - Go to: https://myaccount.google.com/apppasswords
   - If 2-Step Verification is OFF, turn it on first at:
     https://myaccount.google.com/signinoptions/two-step-verification
   - Delete any existing app password for this app
   - Generate a NEW app password
   - Copy the 16-character password (ignore spaces)
   - Update GMAIL_APP_PASSWORD in your .env file

3. CHECK ACCOUNT SECURITY:
   - Go to: https://myaccount.google.com/security
   - Review any security alerts
   - Make sure no suspicious activity blocked access
""")

except Exception as e:
    print(f"\n    FAILED: {type(e).__name__} - {e}")
    import traceback
    traceback.print_exc()
