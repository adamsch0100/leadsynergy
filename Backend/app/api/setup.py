from flask import Blueprint, request, jsonify
from app.service.fub_api_key_service import FUBAPIKeyServiceSingleton
import asyncio
import logging

setup_bp = Blueprint('setup', __name__)
logger = logging.getLogger(__name__)

@setup_bp.route('/fub-api-key', methods=['POST'])
def setup_fub_api_key():
    """Setup or update a user's FUB API key"""
    data = request.get_json()
    if not data or 'api_key' not in data:
        return jsonify({"error": "API key is required"}), 400

    # Get user ID from the request
    user_id = data.get('user_id') or request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    api_key = data['api_key'].strip()
    if not api_key:
        return jsonify({"error": "API key cannot be empty"}), 400

    fub_service = FUBAPIKeyServiceSingleton.get_instance()
    
    # Validate and store the API key (run async function in sync context)
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            fub_service.validate_and_store_api_key(user_id, api_key)
        )
        loop.close()
    except Exception as e:
        return jsonify({
            "error": f"Failed to validate API key: {str(e)}"
        }), 500
    
    if not success:
        return jsonify({
            "error": "Invalid FUB API key. Please check your key and try again."
        }), 400
    
    # Mark onboarding as completed when API key is successfully set
    from app.service.user_service import UserServiceSingleton
    user_service = UserServiceSingleton.get_instance()
    profile = user_service.get_profile(user_id)
    if profile:
        profile.onboarding_completed = True
        user_service.update_profile(profile)

    # Auto-provision FUB team members
    team_result = None
    try:
        from app.service.fub_team_provisioning_service import FUBTeamProvisioningServiceSingleton
        provisioning_service = FUBTeamProvisioningServiceSingleton.get_instance()

        # Get or create organization for this user
        organization_id = provisioning_service.get_or_create_organization(user_id)

        # Provision team members from FUB
        team_result = provisioning_service.provision_team_from_fub(
            broker_user_id=user_id,
            organization_id=organization_id,
            fub_api_key=api_key
        )

        logger.info(
            f"Team provisioning for user {user_id}: "
            f"{team_result.get('provisioned_count', 0)} provisioned, "
            f"{team_result.get('skipped_count', 0)} skipped"
        )
    except Exception as e:
        logger.error(f"Error during team provisioning: {e}")
        # Don't fail the API key setup if team provisioning fails
        team_result = {"error": str(e), "provisioned_count": 0}

    # Auto-create AI custom fields in FUB
    custom_fields_result = None
    try:
        from app.ai_agent.crm_sync_service import CRMSyncService
        from app.database.fub_api_client import FUBApiClient

        fub_client = FUBApiClient(api_key=api_key)
        crm_service = CRMSyncService(fub_client=fub_client)

        org_id = organization_id if 'organization_id' in dir() else None
        loop2 = asyncio.new_event_loop()
        asyncio.set_event_loop(loop2)
        custom_fields_result = loop2.run_until_complete(
            crm_service.auto_create_missing_fields(organization_id=org_id)
        )
        loop2.close()

        created_count = len(custom_fields_result.get("created", []))
        existing_count = len(custom_fields_result.get("existing", []))
        failed_count = len(custom_fields_result.get("failed", []))
        logger.info(
            f"Custom fields for user {user_id}: "
            f"{created_count} created, {existing_count} existed, {failed_count} failed"
        )
    except Exception as e:
        logger.error(f"Error creating custom fields: {e}")
        custom_fields_result = {"error": str(e)}

    return jsonify({
        "message": "FUB API key configured successfully",
        "team_provisioned": team_result,
        "custom_fields": custom_fields_result,
    })

@setup_bp.route('/fub-api-key-status', methods=['GET'])
def get_fub_api_key_status():
    """Check if a user has a valid FUB API key"""
    user_id = request.args.get('user_id') or request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    fub_service = FUBAPIKeyServiceSingleton.get_instance()
    has_api_key = fub_service.has_api_key(user_id)
    
    return jsonify({
        "hasApiKey": has_api_key,
        "userId": user_id
    })

@setup_bp.route('/fub-api-key', methods=['DELETE'])
def remove_fub_api_key():
    """Remove a user's FUB API key"""
    user_id = request.args.get('user_id') or request.headers.get('X-User-ID')
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    fub_service = FUBAPIKeyServiceSingleton.get_instance()
    success = fub_service.remove_api_key(user_id)
    
    if success:
        return jsonify({"message": "FUB API key removed successfully"})
    else:
        return jsonify({"error": "Failed to remove FUB API key"}), 500 