"""LeadSynergy Backend API - Main entry point"""
from flask import Flask, jsonify, request
from app.webhook.fub_webhook_f import (
    webhook_stage_updated_handler,
    webhook_note_created_handler,
    webhook_note_updated_handler,
    webhook_tag_handler,
    webhook_person_created_handler,
    webhook_person_updated_handler,
)
from app.webhook.ai_webhook_handlers import ai_webhook_bp
from app.webhook.stripe_webhook_handler import register_stripe_webhook
from app.integrations.stripe.service import create_checkout_session, create_customer_portal_session
from flask_cors import CORS
import os
import sys
import signal
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
from app.api.setup import setup_bp
from app.api.test import test_bp
from app.api.ai_settings import ai_settings_bp
from app.api.ai_analytics import ai_analytics_bp
from app.api.ai_monitoring import ai_monitoring_bp
from app.api.onboarding import onboarding_bp
from app.billing import billing_bp
from app.enrichment import enrichment_bp
from app.fub import fub_bp
from app.support import support_bp
from app.analytics import analytics_bp
from app.lead_source_mappings import lead_source_mappings_bp

from app.service.supabase_api_service import register_supabase_api
from app.service.supabase_api_service_sse import sse_bp

# Flask-SocketIO and Voice AI are optional (for voice calling feature)
SOCKETIO_AVAILABLE = False
VOICE_AVAILABLE = False
socketio = None

try:
    from flask_socketio import SocketIO
    SOCKETIO_AVAILABLE = True
except ImportError:
    print("Warning: flask-socketio not installed. Voice AI WebSocket disabled.")

try:
    from app.voice import voice_bp, init_voice_socketio
    VOICE_AVAILABLE = True
except ImportError:
    print("Warning: app.voice module not found. Voice AI features disabled.")

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

# Enable CORS to allow requests from our frontend and FUB embedded app
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://localhost:3003",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
    "http://127.0.0.1:3003",
    "https://leadsynergy.ai",
    "https://www.leadsynergy.ai",
    # FUB domains for embedded app
    "https://app.followupboss.com",
    "https://followupboss.com",
    "https://eia.followupboss.com",
]

# Also allow any FUB subdomain (team-specific domains like saahomes.followupboss.com)
FUB_DOMAIN_PATTERN = ".followupboss.com"

# Initialize SocketIO for voice AI WebSocket support
socketio = None
if SOCKETIO_AVAILABLE:
    socketio = SocketIO(
        app,
        cors_allowed_origins=ALLOWED_ORIGINS + ["chrome-extension://*"],
        async_mode='threading',
        logger=False,  # Set to True for debugging
        engineio_logger=False
    )
    # Initialize voice AI SocketIO handlers (if voice module available)
    if VOICE_AVAILABLE:
        init_voice_socketio(socketio)
        app.logger.info("Voice AI WebSocket support enabled")
    else:
        app.logger.info("Voice AI module not available, WebSocket handlers not registered")

CORS(app, resources={r"/*": {
    "origins": ALLOWED_ORIGINS,
    "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    "allow_headers": ["Content-Type", "Authorization", "X-User-ID", "X-Requested-With", "X-FUB-Context", "X-System", "X-System-Key"],
    "supports_credentials": True
}})

# Explicit CORS handler as fallback to ensure headers are always set
@app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin')
    # Allow explicit origins or any FUB subdomain
    is_allowed = origin in ALLOWED_ORIGINS or (origin and FUB_DOMAIN_PATTERN in origin)
    if is_allowed:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-User-ID, X-Requested-With, X-FUB-Context, X-System, X-System-Key'
    return response

# Handle OPTIONS preflight requests explicitly
@app.before_request
def handle_preflight():
    if request.method == 'OPTIONS':
        origin = request.headers.get('Origin')
        is_allowed = origin in ALLOWED_ORIGINS or (origin and FUB_DOMAIN_PATTERN in origin)
        if is_allowed:
            response = app.make_default_options_response()
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS, PATCH'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-User-ID, X-Requested-With, X-FUB-Context, X-System, X-System-Key'
            return response

# Register the setup blueprint
app.register_blueprint(setup_bp, url_prefix='/api/setup')

# Register the test blueprint
app.register_blueprint(test_bp, url_prefix='/api/test')

# Register the AI settings blueprint
app.register_blueprint(ai_settings_bp, url_prefix='/api/ai-settings')

# Register the AI analytics blueprint
app.register_blueprint(ai_analytics_bp, url_prefix='/api/ai-analytics')

# Register the AI monitoring blueprint (for monitoring dashboard)
app.register_blueprint(ai_monitoring_bp, url_prefix='/api/ai-monitoring')

# Register the onboarding blueprint
app.register_blueprint(onboarding_bp)  # Blueprint already has url_prefix='/api/onboarding'

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

# Register the AI webhook handlers (for real-time message processing)
app.register_blueprint(ai_webhook_bp)  # Blueprint already has url_prefix='/webhooks/ai'

# Register the voice AI blueprint (if available)
if VOICE_AVAILABLE:
    app.register_blueprint(voice_bp, url_prefix='/api/voice')

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
app.add_url_rule("/api/billing/portal", "billing_portal", create_customer_portal_session, methods=["POST"])

register_supabase_api(app)
app.register_blueprint(sse_bp, url_prefix='/api/supabase')  # Register SSE endpoints

# Version tracking for deployment verification
DEPLOY_VERSION = "2026-01-29-v16-kill-zombie-chromium"

# Add a basic health check endpoint
@app.route("/")
def root():
    return jsonify({
        "status": "healthy",
        "message": "LeadSynergy API Server",
        "version": DEPLOY_VERSION,
        "timestamp": datetime.now().isoformat(),
    })

@app.route("/health")
def health():
    """
    Health check endpoint for Railway / load balancer monitoring.

    Returns 200 if the server is running and can reach the database.
    Returns 503 if critical dependencies are unreachable.
    """
    checks = {"server": "ok"}
    status_code = 200

    # Check database connectivity
    try:
        from app.database.supabase_client import SupabaseClientSingleton
        supabase = SupabaseClientSingleton.get_instance()
        supabase.table("organizations").select("id").limit(1).execute()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)[:100]}"
        status_code = 503

    checks["version"] = DEPLOY_VERSION
    checks["timestamp"] = datetime.now().isoformat()

    return jsonify(checks), status_code


@app.route("/version")
def version():
    """Version endpoint for deployment verification."""
    return jsonify({
        "version": DEPLOY_VERSION,
        "features": [
            "warm_session_validation",
            "step_level_timeouts",
            "consecutive_failure_recovery",
            "page_state_reset",
            "email_verification_flexible_search",
            "login_rate_limiting_10min_cooldown",
        ],
        "timestamp": datetime.now().isoformat(),
    })

# =====================================================================
# Structured JSON logging for production
# =====================================================================
class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging in production."""
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging():
    """Configure logging — JSON in production, human-readable in development."""
    is_production = os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("FLASK_ENV") == "production"
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    if is_production:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))

    root.addHandler(handler)

    # Reduce noise from chatty libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger("leadsynergy")


# =====================================================================
# Graceful shutdown
# =====================================================================
def graceful_shutdown(signum, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    sig_name = signal.Signals(signum).name
    logger.info(f"Received {sig_name} — shutting down gracefully")
    sys.exit(0)

signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)


if __name__ == "__main__":
    # Get port from environment (Railway sets this) or default to 8000
    port = int(os.environ.get("PORT", 8000))
    # Bind to 0.0.0.0 for Railway (external access) or 127.0.0.1 for local dev
    host = "0.0.0.0" if os.environ.get("RAILWAY_ENVIRONMENT") else "127.0.0.1"

    print("=" * 60)
    print("Starting LeadSynergy API Server...")
    print("=" * 60)
    print("Listening for webhook events...")

    # Log environment info
    print(f"\nEnvironment Configuration:")
    print(f"  Frontend URL: {os.environ.get('FRONTEND_URL', 'Not set')}")
    print(f"  Backend Port: {port}")
    print(f"  Host: {host}")
    print(f"  Railway Environment: {os.environ.get('RAILWAY_ENVIRONMENT', 'Not set')}")
    print(f"  Stripe key configured: {'Yes' if os.environ.get('STRIPE_SECRET_KEY') else 'No'}")
    print(f"  Webhook secret configured: {'Yes' if os.environ.get('STRIPE_WEBHOOK_SECRET') else 'No'}")
    print(f"\nServer starting at: http://{host}:{port}")
    print("=" * 60 + "\n")

    # In production (Railway), use debug=False
    is_production = os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("FLASK_ENV") == "production"

    print(f"Running in {'production' if is_production else 'development'} mode...")
    print(f"  Voice AI WebSocket: {'Enabled' if socketio else 'Disabled'}")
    try:
        # Use SocketIO run if available for WebSocket support
        if socketio:
            socketio.run(app, host=host, port=port, debug=not is_production, use_reloader=False)
        else:
            app.run(host=host, port=port, debug=not is_production, use_reloader=False)
    except OSError as e:
        if "address already in use" in str(e).lower() or "Address already in use" in str(e):
            print(f"\nERROR: Port {port} is already in use!")
            print("Please stop any other process using this port and try again.")
            print(f"Error details: {e}\n")
        else:
            raise
