"""
Debug FUB text messages - find out why they return privacy placeholder.
"""
import os
import sys
import requests
import base64

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Add Backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FUB_API_KEY = os.getenv("FUB_API_KEY")
if not FUB_API_KEY:
    print("ERROR: FUB_API_KEY not set")
    sys.exit(1)

BASE_URL = "https://api.followupboss.com/v1/"
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Basic {base64.b64encode(f"{FUB_API_KEY}:".encode()).decode()}',
}

PERSON_ID = 2099

print("=" * 70)
print("Debugging FUB Text Messages")
print("=" * 70)

# 1. Get recent text messages for this person
print(f"\n1. Fetching text messages for person {PERSON_ID}...")
url = f"{BASE_URL}textMessages?personId={PERSON_ID}&limit=10"
response = requests.get(url, headers=headers)
print(f"   Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    messages = data.get('textmessages', [])
    print(f"   Found {len(messages)} messages")

    for i, msg in enumerate(messages[:5]):
        print(f"\n   Message {i+1}:")
        print(f"      ID: {msg.get('id')}")
        print(f"      Created: {msg.get('created')}")
        print(f"      isIncoming: {msg.get('isIncoming')}")
        print(f"      From: {msg.get('fromNumber')}")
        print(f"      To: {msg.get('toNumber')}")
        content = msg.get('message', '')
        print(f"      Content: {content[:100] if content else 'EMPTY'}")
        if "hidden" in content.lower():
            print(f"      *** PRIVACY REDACTED ***")
else:
    print(f"   ERROR: {response.text}")

# 2. Try fetching a specific message by ID
print(f"\n2. Trying to fetch messages individually...")
if response.status_code == 200 and messages:
    for msg in messages[:3]:
        msg_id = msg.get('id')
        url = f"{BASE_URL}textMessages/{msg_id}"
        resp = requests.get(url, headers=headers)
        print(f"\n   Message ID {msg_id}:")
        print(f"      Status: {resp.status_code}")
        if resp.status_code == 200:
            single_msg = resp.json()
            content = single_msg.get('message', '')
            print(f"      Content: {content[:100] if content else 'EMPTY'}")
            if "hidden" in content.lower():
                print(f"      *** STILL PRIVACY REDACTED ***")
        else:
            print(f"      ERROR: {resp.text}")

# 3. Check API key permissions
print(f"\n3. Checking API key info...")
url = f"{BASE_URL}me"
response = requests.get(url, headers=headers)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    me = response.json()
    print(f"   User: {me.get('name')}")
    print(f"   Email: {me.get('email')}")
    print(f"   Role: {me.get('role')}")
    print(f"   ID: {me.get('id')}")
else:
    print(f"   ERROR: {response.text}")

# 4. Get person details to see if there's something special
print(f"\n4. Getting person {PERSON_ID} details...")
url = f"{BASE_URL}people/{PERSON_ID}"
response = requests.get(url, headers=headers)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    person = response.json()
    print(f"   Name: {person.get('firstName')} {person.get('lastName')}")
    print(f"   Source: {person.get('source')}")
    phones = person.get('phones', [])
    for phone in phones:
        print(f"   Phone: {phone.get('value')} (type: {phone.get('type')})")
else:
    print(f"   ERROR: {response.text}")

print("\n" + "=" * 70)
print("Debug Complete")
print("=" * 70)
