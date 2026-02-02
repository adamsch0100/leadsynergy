import requests
from requests.auth import HTTPBasicAuth
import os
import sys

# from app.utils.constants import Credentials
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)
from app.utils.constants import Credentials

api_key = os.getenv("FUB_API_KEY", "")

# System Names
tag_system_name = "Referral-Link"
stage_system_name = "Referral-Link-Stage"
note_system_name = "Referral-Link-Notes"

# System Keys
tag_system_key = "c90d7c26bbb69a546ceec6bee84c253e"
stage_system_key = "3be2521cfd9598e061f4d736ffb8932b"
note_system_key = "55d34eb8e782e19c46387d008042644d"

url = 'https://api.followupboss.com/v1/webhooks/'
CREDS = Credentials()
headers = {
    'X-System': note_system_name,
    "X-System-Key": note_system_key,
    'Content-Type': 'application/json'
}

payload = {
    'event': 'peopleTagsCreated'  # Event type the webhook listens to
}


def get_webhooks():
    response = requests.get(url, headers=headers, auth=HTTPBasicAuth(api_key, ''))

    if response.status_code == 200:
        webhooks = response.json()
        print(webhooks)
        if webhooks:
            print("Registered Webhooks:")
            # for webhook in webhooks:
            #     print(
            #         f"ID: {webhook['id']}, Event: {webhook['event']}, URL: {webhook['url']}, Status: {webhook['status']}")
        else:
            print("No webhooks registered.")
    else:
        print(f"Failed to retrieve webhooks: {response.status_code} - {response.text}")


def list_webhook_applications():
    """List all webhook applications by system name and their details."""
    response = requests.get(url, headers=headers, auth=HTTPBasicAuth(api_key, ''))

    if response.status_code == 200:
        data = response.json()

        # Extract webhooks from the nested structure
        if 'webhooks' in data and isinstance(data['webhooks'], list):
            webhooks = data['webhooks']

            print("\n=== Webhook Applications ===")
            if webhooks:
                # Group webhooks by system
                webhook_apps = {}
                for webhook in webhooks:
                    system_name = webhook.get('system', 'Unknown System')

                    if system_name not in webhook_apps:
                        webhook_apps[system_name] = []

                    webhook_apps[system_name].append({
                        'id': webhook.get('id'),
                        'event': webhook.get('event'),
                        'url': webhook.get('url'),
                        'status': webhook.get('status')
                    })

                # Print organized results
                for system, hooks in webhook_apps.items():
                    print(f"\nSystem: {system}")
                    print("-" * 50)
                    for hook in hooks:
                        print(f"  ID: {hook['id']}")
                        print(f"  Event: {hook['event']}")
                        print(f"  URL: {hook['url']}")
                        print(f"  Status: {hook['status']}")
                        print("-" * 30)
            else:
                print("No webhooks found.")
        else:
            print("Unexpected response format. No 'webhooks' key found.")
            print(f"Response structure: {data.keys()}")
    else:
        print(f"Failed to retrieve webhooks: {response.status_code} - {response.text}")


def update_webhooks(webhook_id: str = 0):
    # print(f"{url}{webhook_id}")
    response = requests.put(f"{url}{webhook_id}", json=payload, headers=headers, auth=HTTPBasicAuth(api_key, ''))

    if response.status_code in range(200, 300):
        print('Webhook updated successfully.')
        print(response.text)
    else:
        print('Failed to update webhook:', response.text)

def delete_webhook(webhook_id: str = 0):
    response = requests.delete(f"{url}{webhook_id}", json=payload, headers=headers, auth=HTTPBasicAuth(api_key, ''))

    if response.status_code in range(200, 300):
        print('Webhook updated successfully.')
        print(response.text)
    else:
        print('Failed to update webhook:', response.text)


if __name__ == '__main__':
    list_webhook_applications()
    # get_webhooks()
    # delete_webhook("50")
    # delete_webhook("47")
    # delete_webhook("48")
    print('\n\n')
    list_webhook_applications()
    # get_webhooks()
