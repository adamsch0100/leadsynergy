from flask import Flask, jsonify
from app.webhook.fub_webhook_f import (
    webhook_stage_updated_handler,
    webhook_note_created_handler,
    webhook_note_updated_handler,
    webhook_tag_handler,
    webhook_person_created_handler,
    webhook_person_updated_handler,
)
from app.webhook.stripe_webhook_handler import register_stripe_webhook
from app.integrations.stripe.service import create_checkout_session
from flask_cors import CORS
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from app.api.setup import setup_bp
from app.api.test import test_bp
from app.api.ai_settings import ai_settings_bp
from app.api.ai_analytics import ai_analytics_bp
from app.billing import billing_bp
from app.enrichment import enrichment_bp
from app.fub import fub_bp
from app.support import support_bp
from app.analytics import analytics_bp
from app.lead_source_mappings import lead_source_mappings_bp

from app.service.supabase_api_service import register_supabase_api
from app.service.supabase_api_service_sse import sse_bp

# Load environment variables early
load_dotenv()

# Configure logging for better debugging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("stripe_logs.log")],
)

# Set specific loggers
stripe_logger = logging.getLogger("stripe")
stripe_logger.setLevel(logging.DEBUG)

app = Flask(__name__, template_folder='app/templates')

# Log startup
app.logger.info("Starting Follow Up Boss webhook server...")
app.logger.info(f"Server started at: {datetime.now()}")

# Enable CORS to allow requests from our frontend
CORS(app, resources={r"/*": {
    "origins": [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://leadsynergy.ai",
        "https://www.leadsynergy.ai"
    ],
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    "allow_headers": ["Content-Type", "Authorization", "X-User-ID", "X-Requested-With"],
    "supports_credentials": True
}})

# Register the setup blueprint
app.register_blueprint(setup_bp, url_prefix='/api/setup')

# Register the test blueprint
app.register_blueprint(test_bp, url_prefix='/api/test')

# Register the AI settings blueprint
app.register_blueprint(ai_settings_bp, url_prefix='/api/ai-settings')

# Register the AI analytics blueprint
app.register_blueprint(ai_analytics_bp, url_prefix='/api/ai-analytics')

# Register the billing blueprint
app.register_blueprint(billing_bp, url_prefix='/api/billing')

# Register the enrichment blueprint
app.register_blueprint(enrichment_bp, url_prefix='/api/enrichment')

# Register the FUB embedded app blueprint
app.register_blueprint(fub_bp, url_prefix='/fub')

# Register the support ticket blueprint
app.register_blueprint(support_bp, url_prefix='/api/support')

# Register the analytics blueprint
app.register_blueprint(analytics_bp, url_prefix='/api/analytics')

# Register the lead source mappings blueprint
app.register_blueprint(lead_source_mappings_bp, url_prefix='/api/lead-sources')

# Register the webhook routes
app.add_url_rule(
    "/stage-webhook", "stage_webhook", webhook_stage_updated_handler, methods=["POST"]
)
app.add_url_rule(
    "/notes-created-webhook",
    "notes_created_webhook",
    webhook_note_created_handler,
    methods=["POST"],
)
app.add_url_rule(
    "/notes-updated-webhook",
    "notes_updated_webhook",
    webhook_note_updated_handler,
    methods=["POST"],
)
app.add_url_rule("/tag-webhook", "tag_webhook", webhook_tag_handler, methods=["POST"])
app.add_url_rule(
    "/person-created-webhook",
    "person_created_webhook",
    webhook_person_created_handler,
    methods=["POST"],
)
app.add_url_rule(
    "/person-updated-webhook",
    "person_updated_webhook",
    webhook_person_updated_handler,
    methods=["POST"],
)

# Register Stripe webhook and checkout
register_stripe_webhook(app)  # This registers /webhooks/stripe/
app.add_url_rule("/api/checkout", "checkout", create_checkout_session, methods=["POST"])

register_supabase_api(app)
app.register_blueprint(sse_bp, url_prefix='/api/supabase')  # Register SSE endpoints

# Add a basic health check endpoint
@app.route("/")
def root():
    return jsonify({
        "status": "healthy",
        "message": "LeadSynergy API Server",
        "timestamp": datetime.now().isoformat(),
    })

if __name__ == "__main__":
    print("=" * 60)
    print("Starting LeadSynergy API Server...")
    print("=" * 60)
    print("Listening for webhook events...")

    # Log environment info
    print(f"\nEnvironment Configuration:")
    print(f"  Frontend URL: {os.environ.get('FRONTEND_URL', 'Not set')}")
    print(f"  Backend Port: 8000")
    print(f"  Stripe key configured: {'Yes' if os.environ.get('STRIPE_SECRET_KEY') else 'No'}")
    print(f"  Webhook secret configured: {'Yes' if os.environ.get('STRIPE_WEBHOOK_SECRET') else 'No'}")
    print(f"\nServer starting at: http://127.0.0.1:8000")
    print("=" * 60 + "\n")

    # Use Flask development server for reliability
    # Set USE_PRODUCTION_SERVER environment variable to use hypercorn
    use_production = os.environ.get("USE_PRODUCTION_SERVER", "").lower() == "true"

    if use_production:
        try:
            from hypercorn.asyncio import serve
            from hypercorn.config import Config
            import asyncio

            config = Config()
            config.bind = ["127.0.0.1:8000"]
            config.workers = 1
            print("Using Hypercorn server...")
            # Run the server
            asyncio.run(serve(app, config))
        except Exception as e:
            print(f"Hypercorn failed: {e}")
            print("Falling back to Flask development server...")
            app.run(host="127.0.0.1", port=8000, debug=True)
    else:
        print("Using Flask development server...")
        try:
            # Use Flask development server
            app.run(host="127.0.0.1", port=8000, debug=True, use_reloader=False)
        except OSError as e:
            if "address already in use" in str(e).lower() or "Address already in use" in str(e):
                print(f"\nERROR: Port 8000 is already in use!")
                print("Please stop any other process using port 8000 and try again.")
                print(f"Error details: {e}\n")
            else:
                raise
