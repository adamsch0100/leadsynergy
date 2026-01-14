from flask import Flask, request, jsonify
import stripe
import os

# import stripe.error
from app.integrations.stripe.service import stripe_webhook_handler, create_checkout_session

app = Flask(__name__)
stripe.api_key = os.environ['STRIPE_SECRET_KEY']
endpoint_secret = os.environ['STRIPE_WEBHOOK_SECRET']

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    return stripe_webhook_handler()

@app.route('/api/checkout', methods=['POST'])
def checkout():
    return create_checkout_session()