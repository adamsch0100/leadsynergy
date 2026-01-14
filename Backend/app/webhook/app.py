from flask import Flask, request
import hmac
import hashlib
import base64

app = Flask(__name__)


# @app.route('/webhook', methods=['POST'])
# def handle_webhook():
#     data = request.json
#     # Process the webhook data here
#     print('Received webhook:', data)
#     return '', 200

@app.route('/test', methods=['POST'])
def get_test():
    event = request.json
    print(f"Event: {event}")

@app.route('/webhook', methods=['POST'])
def webhook():
    event = request.json
    print(f'Events: {event}')
    event_type = event.get('event_type')
    data = event.get('data')

    if event_type == 'lead.created':
        handle_new_lead(data)
    elif event_type == 'task.updated':
        handle_task_updated(data)
    # Add more event handlers as needed

    return '', 200

def handle_new_lead(data):
    # Process the new lead data
    print(f"New lead created: {data}")

def handle_task_updated(data):
    # Process the updated task data
    print(f"Task updated: {data}")


if __name__ == '__main__':
    app.run(port=5000)
