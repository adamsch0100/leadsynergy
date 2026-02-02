import os
import requests
from requests.auth import HTTPBasicAuth

api_key = os.getenv("FUB_API_KEY", "")

# Custom Domains
custom_domain = "https://www.sec-shit.me"
ngrok_domain = "https://moth-uncommon-minnow.ngrok-free.app"
new_domain = "https://referral-link-backend-production.up.railway.app"

# Event Names
tag_event_name = "peopleTagsCreated"
tag_updated_name = "peopleUpdated"
stage_event_name = "peopleStageUpdated"
stage_created_event_name = "peopleStageCreated"
note_created_event_name = "notesCreated"
note_updated_event_name = "notesUpdated"

# System Names
tag_system_name = "Referral-Link"
stage_system_name = "Referral-Link-Stage"
note_system_name = "Referral-Link-Notes"


def register_webhook(url: str, endpoint: str, event_name: str, system_name: str):
    webhook_url = f"{url}/{endpoint}"

    headers = {
        'Content-Type': 'application/json'
    }

    payload = {
        'event': event_name,
        'url': webhook_url,
        'system': system_name
    }

    response = requests.post(
        'https://api.followupboss.com/v1/webhooks',
        json=payload,
        headers=headers,
        auth=HTTPBasicAuth(api_key, "")
    )

    if response.status_code in range(200, 300):
        print('Webhook registered successfully. With status code: ', response.status_code)
        print(response.text)
    else:
        print('Failed to register webhook:', response.text)


if __name__ == '__main__':
    register_webhook(new_domain, "notes-created-webhook", note_created_event_name, note_system_name)
    # print('Hello Sir')
