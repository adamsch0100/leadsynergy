"""
Onboarding API - Endpoints for the signup and onboarding flow.

This blueprint handles:
- Onboarding status tracking
- Lead source selection and configuration
- Completing onboarding and starting trials
"""

import logging
from flask import Blueprint, request, jsonify
from datetime import datetime

from app.database.supabase_client import SupabaseClientSingleton
from app.service.trial_service import TrialServiceSingleton, TRIAL_CREDITS

logger = logging.getLogger(__name__)

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/api/onboarding')

# Available lead sources with their configuration requirements
LEAD_SOURCES = [
    {
        "id": "homelight",
        "name": "HomeLight",
        "requires_credentials": True,
        "credential_fields": ["email", "password"],
        "requires_2fa": False,
        "description": "HomeLight referral platform"
    },
    {
        "id": "redfin",
        "name": "Redfin",
        "requires_credentials": True,
        "credential_fields": ["email", "password"],
        "requires_2fa": True,
        "two_fa_type": "email_imap",
        "two_fa_fields": ["gmail_email", "gmail_app_password"],
        "description": "Redfin partner referrals"
    },
    {
        "id": "referralexchange",
        "name": "ReferralExchange",
        "requires_credentials": True,
        "credential_fields": ["email", "password"],
        "requires_2fa": False,
        "description": "ReferralExchange platform"
    },
    {
        "id": "agentpronto",
        "name": "Agent Pronto",
        "requires_credentials": True,
        "credential_fields": ["email"],
        "requires_2fa": False,
        "auth_type": "magic_link",
        "description": "Agent Pronto referrals (uses magic link login)"
    },
    {
        "id": "myagentfinder",
        "name": "MyAgentFinder",
        "requires_credentials": True,
        "credential_fields": ["email", "password"],
        "requires_2fa": False,
        "description": "MyAgentFinder platform"
    }
]


def get_user_id_from_request():
    """Extract user ID from request headers."""
    return request.headers.get('X-User-ID')


@onboarding_bp.route('/status', methods=['GET'])
def get_onboarding_status():
    """
    Get current onboarding step and progress.

    Returns:
        {
            "current_step": "fub_api_key" | "lead_sources" | "configure_sources" | "complete",
            "completed_steps": ["fub_api_key", ...],
            "selected_sources": ["homelight", "redfin"],
            "has_fub_api_key": bool,
            "onboarding_completed": bool
        }
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Get user profile
        profile_result = supabase.table('user_profiles').select(
            'onboarding_completed, onboarding_step, selected_lead_sources, fub_api_key'
        ).eq('id', user_id).maybe_single().execute()

        if not profile_result.data:
            # Create default profile if it doesn't exist
            return jsonify({
                "current_step": "fub_api_key",
                "completed_steps": [],
                "selected_sources": [],
                "has_fub_api_key": False,
                "onboarding_completed": False
            })

        profile = profile_result.data

        # Determine completed steps
        completed_steps = []
        if profile.get('fub_api_key'):
            completed_steps.append('fub_api_key')

        selected_sources = profile.get('selected_lead_sources', []) or []
        if selected_sources:
            completed_steps.append('lead_sources')

        # Check if sources are configured
        if selected_sources:
            settings_result = supabase.table('lead_source_settings').select(
                'source_name, is_active'
            ).eq('user_id', user_id).execute()

            configured_sources = [
                s['source_name'].lower().replace(' ', '')
                for s in (settings_result.data or [])
                if s.get('is_active')
            ]

            all_configured = all(
                src.lower().replace(' ', '') in configured_sources
                for src in selected_sources
            )
            if all_configured:
                completed_steps.append('configure_sources')

        current_step = profile.get('onboarding_step', 'fub_api_key')

        return jsonify({
            "current_step": current_step,
            "completed_steps": completed_steps,
            "selected_sources": selected_sources,
            "has_fub_api_key": bool(profile.get('fub_api_key')),
            "onboarding_completed": profile.get('onboarding_completed', False)
        })

    except Exception as e:
        logger.error(f"Error getting onboarding status: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route('/lead-sources', methods=['GET'])
def get_available_lead_sources():
    """
    Get list of available lead sources with their configuration requirements.

    Returns:
        {
            "sources": [
                {
                    "id": "homelight",
                    "name": "HomeLight",
                    "requires_credentials": true,
                    "credential_fields": ["email", "password"],
                    ...
                }
            ]
        }
    """
    return jsonify({
        "sources": LEAD_SOURCES,
        "trial_credits": TRIAL_CREDITS
    })


@onboarding_bp.route('/select-lead-sources', methods=['POST'])
def select_lead_sources():
    """
    Save user's selected lead sources.

    Body:
        {
            "sources": ["homelight", "redfin", "referralexchange"]
        }

    Returns:
        {
            "success": true,
            "selected_sources": ["homelight", "redfin", "referralexchange"]
        }
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    data = request.get_json()
    if not data or 'sources' not in data:
        return jsonify({"error": "Sources list is required"}), 400

    selected_sources = data.get('sources', [])

    # Validate source IDs
    valid_source_ids = {s['id'] for s in LEAD_SOURCES}
    invalid_sources = [s for s in selected_sources if s not in valid_source_ids]
    if invalid_sources:
        return jsonify({
            "error": f"Invalid source IDs: {invalid_sources}",
            "valid_sources": list(valid_source_ids)
        }), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Update user profile
        supabase.table('user_profiles').update({
            'selected_lead_sources': selected_sources,
            'onboarding_step': 'configure_sources' if selected_sources else 'lead_sources',
            'updated_at': datetime.utcnow().isoformat()
        }).eq('id', user_id).execute()

        # Create lead_source_settings entries for each selected source
        for source_id in selected_sources:
            source_info = next((s for s in LEAD_SOURCES if s['id'] == source_id), None)
            if source_info:
                # Check if already exists
                existing = supabase.table('lead_source_settings').select('id').eq(
                    'user_id', user_id
                ).eq('source_name', source_info['name']).maybe_single().execute()

                if not existing.data:
                    supabase.table('lead_source_settings').insert({
                        'user_id': user_id,
                        'source_name': source_info['name'],
                        'is_active': False,
                        'auto_discovered': False,
                        'metadata': {},
                        'created_at': datetime.utcnow().isoformat()
                    }).execute()

        return jsonify({
            "success": True,
            "selected_sources": selected_sources
        })

    except Exception as e:
        logger.error(f"Error selecting lead sources: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route('/configure-source/<source_id>', methods=['POST'])
def configure_lead_source(source_id):
    """
    Configure credentials for a specific lead source.

    Body:
        {
            "email": "user@example.com",
            "password": "secret",
            "two_factor_auth": {
                "enabled": true,
                "email": "gmail@gmail.com",
                "app_password": "xxxx xxxx xxxx xxxx"
            }
        }

    Returns:
        {
            "success": true,
            "source_id": "homelight",
            "configured": true
        }
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    # Find source info
    source_info = next((s for s in LEAD_SOURCES if s['id'] == source_id), None)
    if not source_info:
        return jsonify({"error": f"Unknown source: {source_id}"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Credentials are required"}), 400

    # Validate required fields
    required_fields = source_info.get('credential_fields', [])
    missing_fields = [f for f in required_fields if not data.get(f)]
    if missing_fields:
        return jsonify({
            "error": f"Missing required fields: {missing_fields}",
            "required_fields": required_fields
        }), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Build metadata with credentials
        metadata = {
            "credentials": {
                field: data.get(field)
                for field in required_fields
            }
        }

        # Handle 2FA if required
        if source_info.get('requires_2fa'):
            two_fa_data = data.get('two_factor_auth', {})
            if two_fa_data.get('enabled'):
                metadata['two_factor_auth'] = {
                    'enabled': True,
                    'email': two_fa_data.get('email'),
                    'app_password': two_fa_data.get('app_password')
                }

        # Update or create lead_source_settings
        existing = supabase.table('lead_source_settings').select('id').eq(
            'user_id', user_id
        ).eq('source_name', source_info['name']).maybe_single().execute()

        if existing.data:
            supabase.table('lead_source_settings').update({
                'metadata': metadata,
                'is_active': True,
                'updated_at': datetime.utcnow().isoformat()
            }).eq('id', existing.data['id']).execute()
        else:
            supabase.table('lead_source_settings').insert({
                'user_id': user_id,
                'source_name': source_info['name'],
                'metadata': metadata,
                'is_active': True,
                'auto_discovered': False,
                'created_at': datetime.utcnow().isoformat()
            }).execute()

        logger.info(f"Configured source {source_id} for user {user_id}")

        return jsonify({
            "success": True,
            "source_id": source_id,
            "configured": True
        })

    except Exception as e:
        logger.error(f"Error configuring source {source_id}: {e}")
        return jsonify({"error": str(e)}), 500


@onboarding_bp.route('/complete', methods=['POST'])
def complete_onboarding():
    """
    Complete onboarding and start the trial.

    This endpoint:
    1. Verifies required steps are completed
    2. Creates a trial subscription
    3. Grants trial credits
    4. Marks onboarding as complete

    Returns:
        {
            "success": true,
            "trial": {
                "trial_started": true,
                "trial_ends_at": "2025-01-30T...",
                "credits_granted": {...}
            }
        }
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Get user profile to verify FUB API key is set
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

        # Also update users table
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
def get_trial_status():
    """
    Get trial status for the current user.

    Returns:
        {
            "status": "active" | "expired" | "not_started",
            "ends_at": "2025-01-30T...",
            "days_remaining": 2,
            "credits_remaining": {...}
        }
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        trial_service = TrialServiceSingleton.get_instance()
        status = trial_service.check_trial_status(user_id)

        return jsonify(status)

    except Exception as e:
        logger.error(f"Error getting trial status: {e}")
        return jsonify({"error": str(e)}), 500
