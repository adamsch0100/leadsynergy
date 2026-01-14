"""
Debug script to see exactly what links are in Agent Pronto emails
"""
import imaplib
import email
import re
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

email_address = os.getenv('GMAIL_EMAIL')
app_password = os.getenv('GMAIL_APP_PASSWORD')

print("=" * 60)
print("Agent Pronto Email Debug - Finding All Links")
print("=" * 60)

try:
    # Connect
    connection = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    connection.login(email_address, app_password.replace(" ", ""))
    connection.select("INBOX")

    # Search for Agent Pronto emails - try multiple search terms
    status, message_ids = connection.search(None, 'SUBJECT "Agent Pronto"')
    if not message_ids[0]:
        status, message_ids = connection.search(None, 'SUBJECT "Sign In"')
    if not message_ids[0]:
        status, message_ids = connection.search(None, 'BODY "agentpronto"')

    if status == "OK" and message_ids[0]:
        ids = message_ids[0].split()
        print(f"\nFound {len(ids)} emails from Agent Pronto")

        # Check last 3 emails
        for msg_id in ids[-3:]:
            print("\n" + "=" * 60)
            status, msg_data = connection.fetch(msg_id, "(BODY.PEEK[])")
            if status != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            print(f"From: {msg.get('From')}")
            print(f"Subject: {msg.get('Subject')}")
            print(f"Date: {msg.get('Date')}")

            # Get body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            break
                        except:
                            pass
                    elif part.get_content_type() == "text/html" and not body:
                        try:
                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        except:
                            pass
            else:
                try:
                    body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    pass

            # Find ALL links
            all_links = re.findall(r'(https?://[^\s<>"\']+)', body)
            print(f"\nAll links found ({len(all_links)}):")
            for i, link in enumerate(all_links):
                # Truncate for display
                display = link[:100] + "..." if len(link) > 100 else link
                is_tracking = "lnx." in link.lower() or "click" in link.lower()
                is_agentpronto = "agentpronto" in link.lower()
                marker = ""
                if is_tracking:
                    marker = " [TRACKING]"
                elif is_agentpronto:
                    marker = " [DIRECT]"
                print(f"  {i+1}. {display}{marker}")

            # Look specifically for agentpronto links
            ap_links = [l for l in all_links if "agentpronto" in l.lower()]
            if ap_links:
                print(f"\n\nAgent Pronto links specifically:")
                for link in ap_links:
                    is_tracking = "lnx." in link.lower()
                    print(f"  - {'[TRACKING] ' if is_tracking else '[DIRECT] '}{link}")

    else:
        print("No emails from Agent Pronto found")

    connection.logout()

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
