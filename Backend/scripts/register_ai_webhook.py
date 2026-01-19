# -*- coding: utf-8 -*-
"""
Register AI Webhook with Follow Up Boss.

IMPORTANT: FUB requires system registration before using the webhook API.

SETUP STEPS:
1. Go to: https://apps.followupboss.com/system-registration
2. Register "LeadSynergy" (or your system name)
3. You'll receive a System Key
4. Add to .env: FUB_SYSTEM_KEY=your_key_here
5. Run this script: python -m scripts.register_ai_webhook

Usage:
    python -m scripts.register_ai_webhook
    python -m scripts.register_ai_webhook --list
    python -m scripts.register_ai_webhook --delete-all
"""

import os
import sys
import argparse
import requests
from requests.auth import HTTPBasicAuth

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def get_credentials():
    """Get FUB API credentials."""
    api_key = os.getenv("FUB_API_KEY") or os.getenv("FOLLOWUPBOSS_API_KEY")
    system_key = os.getenv("FUB_SYSTEM_KEY")
    system_name = os.getenv("FUB_SYSTEM_NAME", "LeadSynergy")

    if not api_key:
        print("ERROR: FUB_API_KEY not found in .env")
        sys.exit(1)

    if not system_key:
        print("\n" + "=" * 60)
        print("FUB SYSTEM REGISTRATION REQUIRED")
        print("=" * 60)
        print("""
FUB requires system registration before using the webhook API.

STEPS TO FIX:

1. Go to: https://apps.followupboss.com/system-registration

2. Register your system:
   - System Name: LeadSynergy
   - Description: AI-powered lead follow-up
   - Website: https://leadsynergy.ai

3. Copy the System Key you receive

4. Add to your .env file:
   FUB_SYSTEM_KEY=your_key_here
   FUB_SYSTEM_NAME=LeadSynergy

5. Run this script again
""")
        print("=" * 60 + "\n")
        sys.exit(1)

    return api_key, system_key, system_name


def get_backend_url():
    """Get the backend URL for webhooks."""
    url = os.getenv("BACKEND_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if url:
        if not url.startswith("http"):
            url = f"https://{url}"
        return url
    return "https://leadsynergy-production.up.railway.app"


def get_headers(system_name: str, system_key: str):
    """Get headers for FUB API requests."""
    return {
        'Content-Type': 'application/json',
        'X-System': system_name,
        'X-System-Key': system_key
    }


def list_webhooks(api_key: str, system_name: str, system_key: str):
    """List all registered webhooks."""
    print("\n=== Existing FUB Webhooks ===\n")

    response = requests.get(
        'https://api.followupboss.com/v1/webhooks',
        auth=HTTPBasicAuth(api_key, ""),
        headers=get_headers(system_name, system_key)
    )

    if response.status_code == 200:
        data = response.json()
        webhooks = data.get('webhooks', [])

        if not webhooks:
            print("No webhooks registered.")
            return []

        for wh in webhooks:
            status = "ACTIVE" if wh.get('status') != 'Disabled' else "DISABLED"
            print(f"[{status}] ID: {wh.get('id')}")
            print(f"         Event: {wh.get('event')}")
            print(f"         URL: {wh.get('url')}")
            print(f"         System: {wh.get('system')}")
            print()

        return webhooks
    else:
        print(f"Failed to list webhooks: {response.status_code}")
        print(f"Response: {response.text}")
        return []


def delete_webhook(api_key: str, webhook_id: int, system_name: str, system_key: str):
    """Delete a webhook by ID."""
    response = requests.delete(
        f'https://api.followupboss.com/v1/webhooks/{webhook_id}',
        auth=HTTPBasicAuth(api_key, ""),
        headers=get_headers(system_name, system_key)
    )

    if response.status_code in range(200, 300):
        print(f"Deleted webhook {webhook_id}")
        return True
    else:
        print(f"Failed to delete webhook {webhook_id}: {response.text}")
        return False


def register_webhook(api_key: str, url: str, endpoint: str, event: str,
                     system_name: str, system_key: str):
    """Register a webhook with FUB."""
    webhook_url = f"{url}/{endpoint}"

    payload = {
        'event': event,
        'url': webhook_url,
        'system': system_name
    }

    print(f"Registering webhook:")
    print(f"  Event: {event}")
    print(f"  URL: {webhook_url}")
    print(f"  System: {system_name}")

    response = requests.post(
        'https://api.followupboss.com/v1/webhooks',
        json=payload,
        auth=HTTPBasicAuth(api_key, ""),
        headers=get_headers(system_name, system_key)
    )

    if response.status_code in range(200, 300):
        data = response.json()
        print(f"SUCCESS! Webhook ID: {data.get('id')}")
        return data
    else:
        print(f"FAILED: {response.status_code}")
        print(f"Response: {response.text}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Register AI webhooks with FUB")
    parser.add_argument("--list", action="store_true", help="List existing webhooks")
    parser.add_argument("--delete-all", action="store_true", help="Delete all LeadSynergy webhooks")
    parser.add_argument("--url", type=str, help="Override backend URL")
    args = parser.parse_args()

    api_key, system_key, system_name = get_credentials()
    backend_url = args.url or get_backend_url()

    print(f"\nBackend URL: {backend_url}")
    print(f"System Name: {system_name}")
    print(f"API Key: {api_key[:15]}...{api_key[-4:]}")
    print(f"System Key: {system_key[:10]}...{system_key[-4:] if len(system_key) > 14 else '****'}\n")

    # List existing webhooks
    if args.list:
        list_webhooks(api_key, system_name, system_key)
        return

    # Delete all LeadSynergy webhooks
    if args.delete_all:
        print("Deleting all LeadSynergy webhooks...")
        webhooks = list_webhooks(api_key, system_name, system_key)
        for wh in webhooks:
            if wh.get('system') == system_name:
                delete_webhook(api_key, wh.get('id'), system_name, system_key)
        return

    # Register the AI webhooks
    print("\n=== Registering AI Webhooks ===\n")

    # 1. Text Messages Created - triggers AI response to incoming SMS
    register_webhook(
        api_key=api_key,
        url=backend_url,
        endpoint="webhooks/ai/text-received",
        event="textMessagesCreated",
        system_name=system_name,
        system_key=system_key
    )

    print()

    # 2. People Created - triggers welcome sequence for new leads
    register_webhook(
        api_key=api_key,
        url=backend_url,
        endpoint="webhooks/ai/lead-created",
        event="peopleCreated",
        system_name=system_name,
        system_key=system_key
    )

    print("\n=== Registration Complete ===")
    print("\nTo test:")
    print("1. Reply to the SMS you received earlier")
    print("2. Check server logs for: 'Received text message webhook'")
    print("3. The AI should respond automatically!")


if __name__ == "__main__":
    main()
