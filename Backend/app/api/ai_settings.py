"""
AI Agent Settings API endpoints.

Provides REST API for managing AI agent configuration:
- GET /api/ai-settings - Get current settings
- PUT /api/ai-settings - Update settings
- POST /api/ai-settings/reset - Reset to defaults
"""

from flask import Blueprint, request, jsonify
import asyncio
import logging
from datetime import time

from app.ai_agent.settings_service import (
    AIAgentSettings,
    AIAgentSettingsService,
    get_settings_service,
)
from app.database import get_supabase_client

logger = logging.getLogger(__name__)

ai_settings_bp = Blueprint('ai_settings', __name__)


def run_async(coro):
    """Run async function in sync Flask context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def get_user_info(request_obj):
    """Extract user and organization info from request."""
    # Try to get user ID from various sources
    user_id = (
        request_obj.get_json(silent=True) or {}
    ).get('user_id') or request_obj.headers.get('X-User-ID')

    org_id = (
        request_obj.get_json(silent=True) or {}
    ).get('organization_id') or request_obj.headers.get('X-Organization-ID')

    return user_id, org_id


@ai_settings_bp.route('', methods=['GET'])
def get_settings():
    """
    Get AI agent settings for the current user.

    Query params:
        user_id: Optional user ID
        organization_id: Optional organization ID

    Returns:
        JSON object with current settings
    """
    user_id = request.args.get('user_id') or request.headers.get('X-User-ID')
    org_id = request.args.get('organization_id') or request.headers.get('X-Organization-ID')

    if not user_id and not org_id:
        return jsonify({"error": "User ID or Organization ID is required"}), 400

    try:
        supabase = get_supabase_client()
        service = get_settings_service(supabase)
        settings = run_async(service.get_settings(user_id, org_id))

        return jsonify({
            "success": True,
            "settings": {
                "agent_name": settings.agent_name,
                "brokerage_name": settings.brokerage_name,
                "team_members": settings.team_members,
                "personality_tone": settings.personality_tone,
                "response_delay_seconds": settings.response_delay_seconds,
                "max_response_length": settings.max_response_length,
                "working_hours_start": settings.working_hours_start.strftime('%H:%M'),
                "working_hours_end": settings.working_hours_end.strftime('%H:%M'),
                "timezone": settings.timezone,
                "auto_handoff_score": settings.auto_handoff_score,
                "max_ai_messages_per_lead": settings.max_ai_messages_per_lead,
                "is_enabled": settings.is_enabled,
                "auto_enable_new_leads": settings.auto_enable_new_leads,
                "qualification_questions": settings.qualification_questions,
                "custom_scripts": settings.custom_scripts,
                # Re-engagement settings
                "re_engagement_enabled": settings.re_engagement_enabled,
                "quiet_hours_before_re_engage": settings.quiet_hours_before_re_engage,
                "re_engagement_max_attempts": settings.re_engagement_max_attempts,
                "long_term_nurture_after_days": settings.long_term_nurture_after_days,
                "re_engagement_channels": settings.re_engagement_channels,
                # LLM Model settings
                "llm_provider": settings.llm_provider,
                "llm_model": settings.llm_model,
                "llm_model_fallback": settings.llm_model_fallback,
                # Agent notification
                "notification_fub_person_id": settings.notification_fub_person_id,
                # Phone number filter
                "ai_respond_to_phone_numbers": settings.ai_respond_to_phone_numbers,
            }
        })

    except Exception as e:
        logger.error(f"Error getting AI settings: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@ai_settings_bp.route('', methods=['PUT'])
def update_settings():
    """
    Update AI agent settings.

    Request body:
        user_id: User ID to update settings for
        organization_id: Organization ID (optional)
        ... setting fields to update

    Returns:
        JSON object with updated settings
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    user_id = data.get('user_id') or request.headers.get('X-User-ID')
    org_id = data.get('organization_id') or request.headers.get('X-Organization-ID')

    if not user_id and not org_id:
        return jsonify({"error": "User ID or Organization ID is required"}), 400

    try:
        supabase = get_supabase_client()
        service = get_settings_service(supabase)

        # Get current settings as base
        current_settings = run_async(service.get_settings(user_id, org_id))

        # Update with provided values
        if 'agent_name' in data:
            current_settings.agent_name = data['agent_name']
        if 'brokerage_name' in data:
            current_settings.brokerage_name = data['brokerage_name']
        if 'personality_tone' in data:
            valid_tones = ['friendly_casual', 'professional', 'energetic', 'enthusiastic', 'consultative']
            if data['personality_tone'] not in valid_tones:
                return jsonify({"error": f"Invalid personality_tone. Must be one of: {', '.join(valid_tones)}"}), 400
            current_settings.personality_tone = data['personality_tone']
        if 'response_delay_seconds' in data:
            current_settings.response_delay_seconds = int(data['response_delay_seconds'])
        if 'max_response_length' in data:
            current_settings.max_response_length = int(data['max_response_length'])
        if 'working_hours_start' in data:
            parts = data['working_hours_start'].split(':')
            current_settings.working_hours_start = time(int(parts[0]), int(parts[1]))
        if 'working_hours_end' in data:
            parts = data['working_hours_end'].split(':')
            current_settings.working_hours_end = time(int(parts[0]), int(parts[1]))
        if 'timezone' in data:
            current_settings.timezone = data['timezone']
        if 'auto_handoff_score' in data:
            current_settings.auto_handoff_score = int(data['auto_handoff_score'])
        if 'max_ai_messages_per_lead' in data:
            current_settings.max_ai_messages_per_lead = int(data['max_ai_messages_per_lead'])
        if 'is_enabled' in data:
            current_settings.is_enabled = bool(data['is_enabled'])
        if 'auto_enable_new_leads' in data:
            current_settings.auto_enable_new_leads = bool(data['auto_enable_new_leads'])
        if 'qualification_questions' in data:
            current_settings.qualification_questions = data['qualification_questions']
        if 'custom_scripts' in data:
            current_settings.custom_scripts = data['custom_scripts']
        # Re-engagement settings
        if 're_engagement_enabled' in data:
            current_settings.re_engagement_enabled = bool(data['re_engagement_enabled'])
        if 'quiet_hours_before_re_engage' in data:
            current_settings.quiet_hours_before_re_engage = int(data['quiet_hours_before_re_engage'])
        if 're_engagement_max_attempts' in data:
            current_settings.re_engagement_max_attempts = int(data['re_engagement_max_attempts'])
        if 'long_term_nurture_after_days' in data:
            current_settings.long_term_nurture_after_days = int(data['long_term_nurture_after_days'])
        if 're_engagement_channels' in data:
            current_settings.re_engagement_channels = data['re_engagement_channels']
        # Team members
        if 'team_members' in data:
            current_settings.team_members = data['team_members']
        # LLM Model settings
        if 'llm_provider' in data:
            current_settings.llm_provider = data['llm_provider']
        if 'llm_model' in data:
            current_settings.llm_model = data['llm_model']
        if 'llm_model_fallback' in data:
            current_settings.llm_model_fallback = data['llm_model_fallback']
        # Agent notification
        if 'notification_fub_person_id' in data:
            current_settings.notification_fub_person_id = int(data['notification_fub_person_id']) if data['notification_fub_person_id'] else None
        # Phone number filter
        if 'ai_respond_to_phone_numbers' in data:
            current_settings.ai_respond_to_phone_numbers = data['ai_respond_to_phone_numbers'] if isinstance(data['ai_respond_to_phone_numbers'], list) else []

        # Save settings
        success = run_async(service.save_settings(current_settings, user_id, org_id))

        if success:
            return jsonify({
                "success": True,
                "message": "Settings updated successfully",
                "settings": current_settings.to_dict()
            })
        else:
            return jsonify({"error": "Failed to save settings"}), 500

    except Exception as e:
        logger.error(f"Error updating AI settings: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@ai_settings_bp.route('/reset', methods=['POST'])
def reset_settings():
    """
    Reset AI agent settings to defaults.

    Request body:
        user_id: User ID to reset settings for
        organization_id: Organization ID (optional)

    Returns:
        JSON object with default settings
    """
    data = request.get_json() or {}
    user_id = data.get('user_id') or request.headers.get('X-User-ID')
    org_id = data.get('organization_id') or request.headers.get('X-Organization-ID')

    if not user_id and not org_id:
        return jsonify({"error": "User ID or Organization ID is required"}), 400

    try:
        supabase = get_supabase_client()
        service = get_settings_service(supabase)

        # Create default settings
        default_settings = AIAgentSettings()

        # Save defaults
        success = run_async(service.save_settings(default_settings, user_id, org_id))

        if success:
            return jsonify({
                "success": True,
                "message": "Settings reset to defaults",
                "settings": default_settings.to_dict()
            })
        else:
            return jsonify({"error": "Failed to reset settings"}), 500

    except Exception as e:
        logger.error(f"Error resetting AI settings: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@ai_settings_bp.route('/enabled', methods=['GET'])
def check_enabled():
    """
    Quick check if AI agent is enabled for a user.

    Query params:
        user_id: User ID to check

    Returns:
        JSON object with enabled status
    """
    user_id = request.args.get('user_id') or request.headers.get('X-User-ID')

    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        supabase = get_supabase_client()
        service = get_settings_service(supabase)
        settings = run_async(service.get_settings(user_id))

        return jsonify({
            "enabled": settings.is_enabled,
            "user_id": user_id
        })

    except Exception as e:
        logger.error(f"Error checking AI enabled status: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@ai_settings_bp.route('/toggle', methods=['POST'])
def toggle_enabled():
    """
    Toggle AI agent enabled/disabled.

    Request body:
        user_id: User ID
        enabled: Boolean to set (optional, toggles if not provided)

    Returns:
        JSON object with new enabled status
    """
    data = request.get_json() or {}
    user_id = data.get('user_id') or request.headers.get('X-User-ID')

    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        supabase = get_supabase_client()
        service = get_settings_service(supabase)
        settings = run_async(service.get_settings(user_id))

        # Toggle or set explicit value
        if 'enabled' in data:
            settings.is_enabled = bool(data['enabled'])
        else:
            settings.is_enabled = not settings.is_enabled

        success = run_async(service.save_settings(settings, user_id))

        if success:
            return jsonify({
                "success": True,
                "enabled": settings.is_enabled,
                "message": f"AI agent {'enabled' if settings.is_enabled else 'disabled'}"
            })
        else:
            return jsonify({"error": "Failed to toggle AI status"}), 500

    except Exception as e:
        logger.error(f"Error toggling AI enabled status: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
