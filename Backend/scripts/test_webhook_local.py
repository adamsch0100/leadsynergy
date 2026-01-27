"""
Test the AI webhook handler locally by simulating a FUB webhook call.
"""
import requests
import json

# Local server URL
BASE_URL = "http://localhost:8080"

# Simulated webhook payload (mimics what FUB sends)
webhook_payload = {
    "event": "textMessagesCreated",
    "uri": "https://api.followupboss.com/v1/textMessages?id=12345",
    "resourceIds": [12345],
    "system": {
        "id": "fub",
        "name": "Follow Up Boss"
    }
}

def test_webhook():
    """Send a test webhook to the local server."""
    print("=" * 60)
    print("Testing AI Webhook Handler Locally")
    print("=" * 60)
    
    url = f"{BASE_URL}/webhooks/ai/text-received"
    print(f"\nPOST {url}")
    print(f"Payload: {json.dumps(webhook_payload, indent=2)}")
    
    try:
        response = requests.post(
            url,
            json=webhook_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Body: {response.text}")
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to local server.")
        print("   Make sure you're running: python main.py")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    test_webhook()
