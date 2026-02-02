"""
Onboarding API - Endpoints for the signup and onboarding flow.

This blueprint handles:
- Onboarding status tracking
- Platform info collection (free-text, admin configures later)
- Completing onboarding and starting trials
- Admin endpoints for reviewing setup requests and assigning lead sources
"""

import logging
import re
import threading
from flask import Blueprint, request, jsonify, g
from datetime import datetime

from app.database.supabase_client import SupabaseClientSingleton
from app.service.trial_service import TrialServiceSingleton, TRIAL_CREDITS
from app.middleware.auth import require_auth, _extract_user_id_from_request

logger = logging.getLogger(__name__)


# ─── Platform Detection Helpers ───────────────────────────────────────────────

# Keywords/patterns to detect platforms from free-text descriptions.
# Maps regex patterns -> platform ID. Checked against the customer's description.
_PLATFORM_DETECTION_PATTERNS = [
    (re.compile(r'\bhome\s*light\b', re.IGNORECASE), 'homelight'),
    (re.compile(r'\bred\s*fin\b', re.IGNORECASE), 'redfin'),
    (re.compile(r'\breferral\s*exchange\b', re.IGNORECASE), 'referralexchange'),
    (re.compile(r'\bagent\s*pronto\b', re.IGNORECASE), 'agentpronto'),
    (re.compile(r'\bmy\s*agent\s*finder\b', re.IGNORECASE), 'myagentfinder'),
]


def _detect_platforms(text: str) -> list[str]:
    """Scan free-text for known platform names. Returns list of platform IDs."""
    detected = []
    for pattern, platform_id in _PLATFORM_DETECTION_PATTERNS:
        if pattern.search(text):
            detected.append(platform_id)
    return detected


def _send_setup_request_notification(user_name: str, user_email: str,
                                     platforms_description: str,
                                     detected: list[str]):
    """Send email to admins when a new setup request arrives (background thread)."""
    try:
        from app.email.email_service import EmailServiceSingleton

        supabase = SupabaseClientSingleton.get_instance()

        # Gather admin notification emails (same pattern as support ticket notifications)
        admin_result = supabase.table('users').select('id').in_(
            'role', ['admin', 'broker']
        ).execute()

        notification_emails = []
        for admin in (admin_result.data or []):
            settings = supabase.table('ai_agent_settings').select(
                'support_notification_emails'
            ).eq('user_id', admin['id']).maybe_single().execute()
            if settings.data and settings.data.get('support_notification_emails'):
                notification_emails.extend(settings.data['support_notification_emails'])

        if not notification_emails:
            logger.info("No admin notification emails configured — skipping setup request alert")
            return

        detected_html = ""
        if detected:
            platform_names = [SUPPORTED_PLATFORMS[p]['name'] for p in detected if p in SUPPORTED_PLATFORMS]
            detected_html = f"<p><strong>Auto-detected platforms:</strong> {', '.join(platform_names)}</p>"

        html_body = f"""
        <div style="font-family: sans-serif; max-width: 600px;">
            <h2 style="color: #1e40af;">New Setup Request</h2>
            <p>A new customer has signed up and needs lead source configuration.</p>
            <table style="border-collapse: collapse; width: 100%; margin: 16px 0;">
                <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #e5e7eb;">Customer</td>
                    <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{user_name or 'N/A'} ({user_email})</td></tr>
                <tr><td style="padding: 8px; font-weight: bold; border-bottom: 1px solid #e5e7eb;">Platform Info</td>
                    <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{platforms_description}</td></tr>
            </table>
            {detected_html}
            <p>Log in to the admin dashboard to review and assign lead sources:</p>
            <p><a href="https://app.leadsynergy.com/admin/setup-requests"
                   style="background: #2563eb; color: white; padding: 10px 20px; border-radius: 6px;
                          text-decoration: none; display: inline-block;">Review Setup Requests</a></p>
        </div>
        """

        email_service = EmailServiceSingleton.get_instance()
        for email_addr in set(notification_emails):
            try:
                email_service.send_email(
                    to_email=email_addr,
                    subject=f"New Setup Request: {user_name or user_email}",
                    html_content=html_body,
                    text_content=f"New setup request from {user_name} ({user_email}): {platforms_description}",
                )
                logger.info(f"Setup request notification sent to {email_addr}")
            except Exception as e:
                logger.error(f"Failed to send setup notification to {email_addr}: {e}")

    except Exception as e:
        logger.error(f"Error sending setup request notification: {e}")

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/api/onboarding')

# Internal-only: platform config used by admin when assigning sources.
# NEVER expose this list to customer-facing endpoints.
SUPPORTED_PLATFORMS = {
    "homelight": {
        "name": "HomeLight",
        "credential_fields": ["email", "password"],
        "requires_2fa": False,
    },
    "redfin": {
        "name": "Redfin",
        "credential_fields": ["email", "password"],
        "requires_2fa": True,
        "two_fa_type": "email_imap",
        "two_fa_fields": ["gmail_email", "gmail_app_password"],
    },
    "referralexchange": {
        "name": "ReferralExchange",
        "credential_fields": ["email", "password"],
        "requires_2fa": False,
    },
    "agentpronto": {
        "name": "Agent Pronto",
        "credential_fields": ["email"],
        "requires_2fa": False,
        "auth_type": "magic_link",
    },
    "myagentfinder": {
        "name": "MyAgentFinder",
        "credential_fields": ["email", "password"],
        "requires_2fa": False,
    },
}


def get_user_id_from_request():
    """Extract user ID from request — JWT-aware with header fallback."""
    return _extract_user_id_from_request() or getattr(g, 'user_id', None)


# ─── Customer-Facing Endpoints ───────────────────────────────────────────────

@onboarding_bp.route('/status', methods=['GET'])
@require_auth
def get_onboarding_status():
    """Get current onboarding step and progress."""
    user_id = g.user_id

    try:
        supabase = SupabaseClientSingleton.get_instance()

        profile_result = supabase.table('user_profiles').select(
            'onboarding_completed, onboarding_step, fub_api_key, platforms_description'
        ).eq('id', user_id).maybe_single().execute()

        if not profile_result.data:
            return jsonify({
                "success": True,
                "data": {
                    "current_step": "fub_api_key",
                    "is_complete": False,
                    "fub_api_key": None,
                }
            })

        profile = profile_result.data
        current_step = profile.get('onboarding_step', 'fub_api_key')

        return jsonify({
            "success": True,
            "data": {
                "current_step": current_step,
                "is_complete": profile.get('onboarding_completed', False),
                "fub_api_key": profile.get('fub_api_key'),
            }
        })

    except Exception as e:
        logger.error(f"Error getting onboarding status: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route('/submit-platform-info', methods=['POST'])
@require_auth
def submit_platform_info():
    """
    Save the customer's free-text description of their referral platforms.
    Admin will review this later and configure integrations.
    """
    user_id = g.user_id

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    platforms_description = (data.get('platforms_description') or '').strip()
    if not platforms_description:
        return jsonify({"error": "Please describe your platforms"}), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Auto-detect platform keywords from the free-text description
        detected = _detect_platforms(platforms_description)

        # Save to user profile
        supabase.table('user_profiles').update({
            'platforms_description': platforms_description,
            'onboarding_step': 'lead_sources_info',
            'updated_at': datetime.utcnow().isoformat(),
        }).eq('id', user_id).execute()

        # Create a setup request for admin review
        org_result = supabase.table('organization_users').select(
            'organization_id'
        ).eq('user_id', user_id).limit(1).execute()

        organization_id = org_result.data[0]['organization_id'] if org_result.data else None

        # Get user info for the request
        user_result = supabase.table('users').select(
            'email, full_name'
        ).eq('id', user_id).maybe_single().execute()

        user_email = user_result.data.get('email', '') if user_result.data else ''
        user_name = user_result.data.get('full_name', '') if user_result.data else ''

        # Upsert setup request (includes detected platforms)
        existing = supabase.table('setup_requests').select('id').eq(
            'user_id', user_id
        ).maybe_single().execute()

        request_data = {
            'user_id': user_id,
            'organization_id': organization_id,
            'user_email': user_email,
            'user_name': user_name,
            'platforms_description': platforms_description,
            'detected_platforms': detected,
            'status': 'pending',
            'updated_at': datetime.utcnow().isoformat(),
        }

        if existing and existing.data:
            supabase.table('setup_requests').update(request_data).eq(
                'id', existing.data['id']
            ).execute()
        else:
            request_data['created_at'] = datetime.utcnow().isoformat()
            supabase.table('setup_requests').insert(request_data).execute()

        logger.info(f"Platform info submitted for user {user_id} (detected: {detected})")

        # Send email notification to admin in background
        thread = threading.Thread(
            target=_send_setup_request_notification,
            args=(user_name, user_email, platforms_description, detected),
            daemon=True,
        )
        thread.start()

        return jsonify({"success": True, "detected_platforms": detected})

    except Exception as e:
        logger.error(f"Error submitting platform info: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route('/complete', methods=['POST'])
@require_auth
def complete_onboarding():
    """
    Complete onboarding and start the trial.

    Only requires FUB API key. Lead source configuration is handled
    by admin after reviewing the customer's platform info.
    """
    user_id = g.user_id

    try:
        supabase = SupabaseClientSingleton.get_instance()

        profile_result = supabase.table('user_profiles').select(
            'fub_api_key, onboarding_completed'
        ).eq('id', user_id).maybe_single().execute()

        if not profile_result.data:
            return jsonify({"error": "User profile not found"}), 404

        if not profile_result.data.get('fub_api_key'):
            return jsonify({
                "error": "FUB API key is required before completing onboarding",
                "missing_step": "fub_api_key"
            }), 400

        if profile_result.data.get('onboarding_completed'):
            return jsonify({
                "success": True,
                "message": "Onboarding already completed"
            })

        # Get organization ID for subscription
        org_result = supabase.table('organization_users').select(
            'organization_id'
        ).eq('user_id', user_id).limit(1).execute()

        organization_id = org_result.data[0]['organization_id'] if org_result.data else None

        # Start trial
        trial_service = TrialServiceSingleton.get_instance()
        trial_result = trial_service.start_trial(user_id, organization_id)

        # Mark onboarding as complete
        supabase.table('user_profiles').update({
            'onboarding_completed': True,
            'onboarding_step': 'complete',
            'updated_at': datetime.utcnow().isoformat()
        }).eq('id', user_id).execute()

        supabase.table('users').update({
            'updated_at': datetime.utcnow().isoformat()
        }).eq('id', user_id).execute()

        logger.info(f"Completed onboarding for user {user_id}")

        return jsonify({
            "success": True,
            "trial": trial_result,
            "onboarding_completed": True
        })

    except Exception as e:
        logger.error(f"Error completing onboarding: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route('/trial-status', methods=['GET'])
@require_auth
def get_trial_status():
    """Get trial status for the current user."""
    user_id = g.user_id

    try:
        trial_service = TrialServiceSingleton.get_instance()
        status = trial_service.check_trial_status(user_id)
        return jsonify(status)

    except Exception as e:
        logger.error(f"Error getting trial status: {e}")
        return jsonify({"error": str(e)}), 500


# ─── Admin Endpoints ─────────────────────────────────────────────────────────

@onboarding_bp.route('/admin/setup-requests', methods=['GET'])
@require_auth
def admin_get_setup_requests():
    """
    Admin: List all pending setup requests from new customers.

    Query params:
        status: filter by status (pending, in_progress, completed). Default: all.
    """
    # TODO: Add proper admin role check. For now, any authenticated user.
    status_filter = request.args.get('status')

    try:
        supabase = SupabaseClientSingleton.get_instance()

        query = supabase.table('setup_requests').select('*').order(
            'created_at', desc=True
        )

        if status_filter:
            query = query.eq('status', status_filter)

        result = query.execute()

        return jsonify({
            "success": True,
            "data": result.data or []
        })

    except Exception as e:
        logger.error(f"Error fetching setup requests: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route('/admin/setup-requests/<request_id>', methods=['PATCH'])
@require_auth
def admin_update_setup_request(request_id):
    """
    Admin: Update a setup request status and add notes.

    Body:
        {
            "status": "in_progress" | "completed",
            "admin_notes": "Configured HomeLight and ReferralExchange"
        }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        updates = {'updated_at': datetime.utcnow().isoformat()}

        if 'status' in data:
            if data['status'] not in ('pending', 'in_progress', 'completed'):
                return jsonify({"error": "Invalid status"}), 400
            updates['status'] = data['status']

        if 'admin_notes' in data:
            updates['admin_notes'] = data['admin_notes']

        supabase.table('setup_requests').update(updates).eq(
            'id', request_id
        ).execute()

        return jsonify({"success": True})

    except Exception as e:
        logger.error(f"Error updating setup request: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route('/admin/assign-source', methods=['POST'])
@require_auth
def admin_assign_lead_source():
    """
    Admin: Assign a lead source to a customer and configure credentials.

    Body:
        {
            "user_id": "uuid",
            "platform": "homelight",
            "credentials": {
                "email": "user@example.com",
                "password": "secret"
            },
            "two_factor_auth": {  // optional
                "enabled": true,
                "email": "...",
                "app_password": "..."
            }
        }
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400

    target_user_id = data.get('user_id')
    platform_id = data.get('platform')
    credentials = data.get('credentials', {})

    if not target_user_id or not platform_id:
        return jsonify({"error": "user_id and platform are required"}), 400

    platform_config = SUPPORTED_PLATFORMS.get(platform_id)
    if not platform_config:
        return jsonify({"error": f"Unknown platform: {platform_id}"}), 400

    # Validate required credential fields
    required_fields = platform_config.get('credential_fields', [])
    missing = [f for f in required_fields if not credentials.get(f)]
    if missing:
        return jsonify({
            "error": f"Missing credentials: {missing}",
            "required_fields": required_fields
        }), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        metadata = {
            "credentials": {
                field: credentials[field] for field in required_fields
            }
        }

        # Handle 2FA if provided
        two_fa_data = data.get('two_factor_auth', {})
        if two_fa_data.get('enabled') and platform_config.get('requires_2fa'):
            metadata['two_factor_auth'] = {
                'enabled': True,
                'email': two_fa_data.get('email'),
                'app_password': two_fa_data.get('app_password'),
            }

        source_name = platform_config['name']

        # Upsert lead_source_settings
        existing = supabase.table('lead_source_settings').select('id').eq(
            'user_id', target_user_id
        ).eq('source_name', source_name).maybe_single().execute()

        if existing and existing.data:
            supabase.table('lead_source_settings').update({
                'metadata': metadata,
                'is_active': True,
                'updated_at': datetime.utcnow().isoformat(),
            }).eq('id', existing.data['id']).execute()
        else:
            supabase.table('lead_source_settings').insert({
                'user_id': target_user_id,
                'source_name': source_name,
                'metadata': metadata,
                'is_active': True,
                'auto_discovered': False,
                'created_at': datetime.utcnow().isoformat(),
            }).execute()

        logger.info(f"Admin assigned {platform_id} to user {target_user_id}")

        return jsonify({
            "success": True,
            "platform": platform_id,
            "source_name": source_name,
        })

    except Exception as e:
        logger.error(f"Error assigning source: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route('/admin/supported-platforms', methods=['GET'])
@require_auth
def admin_get_supported_platforms():
    """
    Admin-only: Get list of supported platforms for source assignment.
    Only returns platform IDs and names, not full config details.
    """
    platforms = [
        {"id": pid, "name": cfg["name"], "requires_2fa": cfg.get("requires_2fa", False)}
        for pid, cfg in SUPPORTED_PLATFORMS.items()
    ]
    return jsonify({"success": True, "data": platforms})
