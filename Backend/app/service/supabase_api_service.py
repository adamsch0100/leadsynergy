from flask import Blueprint, jsonify, request
from app.database.supabase_client import SupabaseClientSingleton
from app.middleware.fub_api_key_middleware import fub_api_key_required
from app.service.lead_service import LeadServiceSingleton
from app.service.commission_service import CommissionServiceSingleton
from app.service.organization_service import OrganizationServiceSingleton
from app.service.user_service import UserServiceSingleton
from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
from app.models.lead import Lead
from app.models.commission_submission import CommissionSubmission
from app.service.team_member_service import TeamMemberServiceSingleton
from app.service.system_settings_service import SystemSettingsServiceSingleton
from app.service.notification_settings_service import (
    NotificationSettingsServiceSingleton,
)
from app.models.user import UserProfile
import logging
from datetime import datetime
import uuid
import json
from app.service.subscription_service import SubscriptionService
from app.billing.credit_service import CreditServiceSingleton

supabase_api = Blueprint("supabase_api", __name__, url_prefix="/api/supabase")

# Services
lead_service = LeadServiceSingleton.get_instance()
commission_service = CommissionServiceSingleton.get_instance()
user_service = UserServiceSingleton.get_instance()
org_service = OrganizationServiceSingleton.get_instance()
lead_source_service = LeadSourceSettingsSingleton.get_instance()
team_member_service = TeamMemberServiceSingleton.get_instance()
system_settings_service = SystemSettingsServiceSingleton.get_instance()
notification_settings_service = NotificationSettingsServiceSingleton.get_instance()
subscription_service = SubscriptionService()
credit_service = CreditServiceSingleton.get_instance()

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def serialize_for_json(obj):
    """Convert an object to JSON-serializable format, handling datetime"""
    if obj is None:
        return None
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    if hasattr(obj, 'to_dict'):
        return serialize_for_json(obj.to_dict())
    return obj


@supabase_api.route("/auth/status", methods=["GET"])
def get_auth_status():
    """Check authentication status and onboarding completion"""
    try:
        # Get user ID from token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({
                "success": False, 
                "authenticated": False,
                "error": "Invalid authorization header"
            }), 401

        token = auth_header.split(" ")[1]

        # Use Supabase client to verify token and get user ID
        supabase = SupabaseClientSingleton.get_instance()
        try:
            # Get user from token
            user_response = supabase.auth.get_user(token)
            user_id = user_response.user.id
            user_email = user_response.user.email
        except Exception as auth_error:
            logger.error(f"Token verification error: {str(auth_error)}")
            return jsonify({
                "success": False, 
                "authenticated": False,
                "error": "Invalid or expired token"
            }), 401

        # Get user profile to check onboarding status
        profile = user_service.get_profile(user_id)
        
        # If no profile exists, create one with default onboarding_completed = False
        if not profile:
            user = user_service.get_by_id(user_id)
            if user:
                profile = UserProfile()
                profile.id = user_id
                profile.email = user_email
                profile.full_name = user.full_name if user else None
                profile.phone_number = user.phone_number if user else None
                profile.role = user.role if user else "user"
                profile.onboarding_completed = False
                profile.fub_api_key = None
                profile = user_service.create_profile(profile)
            else:
                # Create basic profile if user doesn't exist in users table
                profile = UserProfile()
                profile.id = user_id
                profile.email = user_email
                profile.onboarding_completed = False
                profile.fub_api_key = None
                profile = user_service.create_profile(profile)

        # Determine if onboarding is required
        requires_onboarding = not profile.onboarding_completed or not profile.fub_api_key
        
        # Determine redirect path
        redirect_path = "/setup/api-key" if requires_onboarding else "/dashboard"

        return jsonify({
            "success": True,
            "authenticated": True,
            "user_id": user_id,
            "email": user_email,
            "requires_onboarding": requires_onboarding,
            "redirect_path": redirect_path,
            "onboarding_completed": profile.onboarding_completed,
            "has_fub_api_key": bool(profile.fub_api_key)
        }), 200

    except Exception as e:
        logger.error(f"Error in get_auth_status: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/users", methods=["GET"])
def get_users():
    try:
        users = user_service.get_all()

        # Convert models to dicts
        user_dicts = [user.to_dict() for user in users]

        return jsonify({"success": True, "data": user_dicts}), 200
    except Exception as e:
        return jsonify({"success": False, "data": str(e)}), 500


@supabase_api.route("/users/<user_id>", methods=["GET"])
def get_user_by_id(user_id):
    try:
        user = user_service.get_by_id(user_id)

        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        return jsonify({"success": True, "data": user.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/users/email/<email>", methods=["GET"])
def get_user_by_email(email):
    try:
        user = user_service.get_by_email(email)

        if not user:
            return jsonify({"success": False, "error": "User not found"}), 404

        return jsonify({"success": True, "data": user.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/users/agents", methods=["GET"])
def get_agents():
    try:
        agents = user_service.get_agents()

        # Convert models to dicts
        agents_dicts = [agent.to_dict() for agent in agents]

        return jsonify({"success": True, "data": agents_dicts}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/users/<user_id>/profile", methods=["GET"])
def get_user_profile(user_id):
    try:
        profile = user_service.get_profile(user_id)

        if not profile:
            return jsonify({"success": False, "error": "User profile not found"}), 404

        return jsonify({"success": True, "data": profile.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/leads", methods=["GET"])
@fub_api_key_required
def get_leads():
    try:
        lead_service = LeadServiceSingleton.get_instance()

        # Get parameters from request for filtering
        filters = {}
        for param in ["source", "status", "assigned_agent_id"]:
            if request.args.get(param):
                filters[param] = request.args.get(param)

        # Get pagination parameters
        limit = int(request.args.get("limit", 100))
        offset = int(request.args.get("offset", 0))

        # Get leads from the service
        leads = lead_service.get_all(filters, limit, offset)

        # Convert leads to dictionaries
        lead_dicts = [lead.to_dict() for lead in leads] if leads else []

        return jsonify({"success": True, "data": lead_dicts}), 200
    except Exception as e:
        print(f"Error fetching leads: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/leads/<lead_id>", methods=["GET"])
@fub_api_key_required
def get_lead_by_id(lead_id):
    try:
        lead = lead_service.get_by_fub_person_id(lead_id)

        if not lead:
            return jsonify({"success": False, "error": "Lead not found"}), 404

        return jsonify({"success": True, "data": lead.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/leads/agent/<agent_id>", methods=["GET"])
@fub_api_key_required
def get_leads_by_agent(agent_id):
    try:
        lead_service = LeadServiceSingleton.get_instance()

        # Get pagination parameters
        limit = int(request.args.get("limit", 100))
        offset = int(request.args.get("offset", 0))

        # Get leads assigned to the agent
        leads = lead_service.get_by_agent_id(agent_id, limit, offset)

        # Convert leads to dictionaries
        lead_dicts = [lead.to_dict() for lead in leads] if leads else []

        return jsonify({"success": True, "data": lead_dicts}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/leads/<lead_id>/with-notes", methods=["GET"])
@fub_api_key_required
def get_lead_with_notes(lead_id):
    try:
        lead_service = LeadServiceSingleton.get_instance()
        lead_with_notes = lead_service.get_with_notes(lead_id)

        if not lead_with_notes:
            return jsonify({"success": False, "error": "Lead not found"}), 404

        return jsonify({"success": True, "data": lead_with_notes}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/leads/<lead_id>/assign", methods=["POST"])
@fub_api_key_required
def assign_lead_to_agent(lead_id):
    try:
        data = request.json
        agent_id = data.get("agent_id")

        if not agent_id:
            return jsonify({"success": False, "error": "agent_id is required"}), 400

        lead_service = LeadServiceSingleton.get_instance()
        updated_lead = lead_service.assign_to_agent(lead_id, agent_id)

        if not updated_lead:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Lead not found or could not be updated",
                    }
                ),
                404,
            )

        return jsonify({"success": True, "data": updated_lead.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/leads/<lead_id>/stage", methods=["PATCH"])
@fub_api_key_required
def update_lead_stage(lead_id):
    try:
        data = request.json
        stage_id = data.get("stage_id")

        if not stage_id:
            return jsonify({"success": False, "error": "stage_id is required"}), 400

        lead_service = LeadServiceSingleton.get_instance()
        updated_lead = lead_service.update_stage(lead_id, stage_id)

        if not updated_lead:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Lead not found or could not be updated",
                    }
                ),
                404,
            )

        return jsonify({"success": True, "data": updated_lead.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/leads/<lead_id>/status", methods=["PATCH"])
@fub_api_key_required
def update_lead_status(lead_id):
    try:
        data = request.json
        status = data.get("status")

        if not status:
            return jsonify({"success": False, "error": "status is required"}), 400

        lead_service = LeadServiceSingleton.get_instance()
        updated_lead = lead_service.update_status(lead_id, status)

        if not updated_lead:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Lead not found or could not be updated",
                    }
                ),
                404,
            )

        return jsonify({"success": True, "data": updated_lead.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Lead Sources
@supabase_api.route("/lead-sources/<source_id>/assignment-strategy", methods=["PUT"])
def update_lead_source_assignment_strategy(source_id):
    try:
        # Get user_id from request
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        logger.info(f"Updating assignment strategy for source ID: {source_id}")
        data = request.json

        # Log the incoming request data
        logger.info(f"Request data: {data}")

        assignment_strategy = data.get("assignment_strategy")
        logger.info(f"Assignment strategy: {assignment_strategy}")

        if not assignment_strategy:
            logger.warning("Missing assignment_strategy in request")
            return (
                jsonify({"success": False, "error": "assignment_strategy is required"}),
                400,
            )

        # Get source first to verify it exists
        source = lead_source_service.get_by_id(source_id)
        if not source:
            logger.warning(f"Lead source not found with ID: {source_id}")
            return (
                jsonify({"success": False, "error": "Lead source not found"}),
                404,
            )

        logger.info(f"Found lead source: {source}")

        # Use Supabase client directly with detailed error handling
        try:
            supabase = SupabaseClientSingleton.get_instance()

            # Log the query we're about to execute
            logger.info(
                f"Executing update on lead_source_settings for id={source_id} with strategy={assignment_strategy}"
            )

            result = (
                supabase.table("lead_source_settings")
                .update(
                    {"assignment_strategy": assignment_strategy, "updated_at": "now()"}
                )
                .eq("id", source_id)
                .execute()
            )

            logger.info(f"Update result: {result}")

            if not result.data or len(result.data) == 0:
                logger.error(f"Update returned no data: {result}")
                return (
                    jsonify(
                        {"success": False, "error": "Lead source could not be updated"}
                    ),
                    500,
                )

            # Return the updated source
            updated_source = lead_source_service.get_by_id(source_id)

            # Convert to dict if not already
            if not isinstance(updated_source, dict):
                updated_source_dict = updated_source.to_dict()
            else:
                updated_source_dict = updated_source

            logger.info(
                f"Successfully updated assignment strategy. Returning: {updated_source_dict}"
            )
            return jsonify({"success": True, "data": updated_source_dict}), 200

        except Exception as db_error:
            logger.error(f"Database error during update: {str(db_error)}")
            return (
                jsonify(
                    {"success": False, "error": f"Database error: {str(db_error)}"}
                ),
                500,
            )

    except Exception as e:
        logger.error(
            f"Unexpected error in update_assignment_strategy: {str(e)}", exc_info=True
        )
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/lead-sources/<source_id>/assignment-rules", methods=["PUT"])
def update_lead_source_assignment_rules(source_id):
    try:
        logger.info(f"Updating assignment rules for source ID: {source_id}")
        data = request.json

        # Log the incoming request data
        logger.info(f"Request data: {data}")

        assignment_rules = data.get("assignment_rules")
        logger.info(f"Assignment rules: {assignment_rules}")

        if assignment_rules is None:
            logger.warning("Missing assignment_rules in request")
            return (
                jsonify({"success": False, "error": "assignment_rules is required"}),
                400,
            )

        # Get source first to verify it exists
        source = lead_source_service.get_by_id(source_id)
        if not source:
            logger.warning(f"Lead source not found with ID: {source_id}")
            return (
                jsonify({"success": False, "error": "Lead source not found"}),
                404,
            )

        logger.info(f"Found lead source: {source}")

        # Use Supabase client directly with detailed error handling
        try:
            supabase = SupabaseClientSingleton.get_instance()

            # Ensure rules is properly serialized as JSON
            if not isinstance(assignment_rules, str):
                import json

                rules_json = json.dumps(assignment_rules)
            else:
                rules_json = assignment_rules

            # Log the query we're about to execute
            logger.info(
                f"Executing update on lead_source_settings for id={source_id} with rules={rules_json}"
            )

            result = (
                supabase.table("lead_source_settings")
                .update({"assignment_rules": rules_json, "updated_at": "now()"})
                .eq("id", source_id)
                .execute()
            )

            logger.info(f"Update result: {result}")

            if not result.data or len(result.data) == 0:
                logger.error(f"Update returned no data: {result}")
                return (
                    jsonify(
                        {"success": False, "error": "Lead source could not be updated"}
                    ),
                    500,
                )

            # Return the updated source
            updated_source = lead_source_service.get_by_id(source_id)

            # Convert to dict if not already
            if not isinstance(updated_source, dict):
                updated_source_dict = updated_source.to_dict()
            else:
                updated_source_dict = updated_source

            logger.info(
                f"Successfully updated assignment rules. Returning: {updated_source_dict}"
            )
            return jsonify({"success": True, "data": updated_source_dict}), 200

        except Exception as db_error:
            logger.error(f"Database error during update: {str(db_error)}")
            return (
                jsonify(
                    {"success": False, "error": f"Database error: {str(db_error)}"}
                ),
                500,
            )

    except Exception as e:
        logger.error(
            f"Unexpected error in update_assignment_rules: {str(e)}", exc_info=True
        )
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/commissions", methods=["GET"])
def get_commissions():
    try:
        commissions = commission_service.get_all()

        commission_dicts = [commission.to_dict() for commission in commissions]

        return jsonify({"success": True, "data": commission_dicts}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/commissions/<commission_id>", methods=["GET"])
def get_commission_by_id(commission_id):
    try:
        commission = commission_service.get_by_id(commission_id)

        if not commission:
            return (
                jsonify({"success": True, "error": "Commission submission not found"}),
                404,
            )

        return jsonify({"success": True, "data": commission.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/commissions/agent/<agent_id>", methods=["GET"])
def get_commissions_by_agent(agent_id):
    try:
        commissions = commission_service.get_by_agent_id(agent_id)

        commission_dicts = (
            [commission.to_dict() for commission in commissions] if commissions else []
        )

        return jsonify({"success": True, "data": commission_dicts}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Organization endpoints
@supabase_api.route("/organizations", methods=["GET"])
def get_organizations():
    try:
        orgs = org_service.get_all()

        org_dicts = [org.to_dict() for org in orgs] if orgs else []

        return jsonify({"success": True, "data": org_dicts}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/organizations/<org_id>", methods=["GET"])
def get_organization_by_id(org_id):
    try:
        org = org_service.get_by_id(org_id)

        if not org:
            return jsonify({"success": False, "error": "Organization not found"}), 404

        return jsonify({"success": True, "data": org.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/organizations/slug/<slug>", methods=["GET"])
def get_organization_by_slug(slug):
    try:
        org = org_service.get_by_slug(slug)

        if not org:
            return jsonify({"success": False, "error": "Organization not found"}), 404

        return jsonify({"success": True, "data": org.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/organizations/<org_id>/users", methods=["GET"])
def get_organization_users(org_id):
    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Get users belonging to this organization with their user details
        result = (
            supabase.table("organization_users")
            .select("*, users(*)")
            .eq("organization_id", org_id)
            .execute()
        )

        return jsonify({"success": True, "data": result.data}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/organizations/<org_id>", methods=["PUT"])
def update_organization(org_id):
    try:
        supabase = SupabaseClientSingleton.get_instance()
        data = request.json

        # Prepare update data
        update_data = {
            "updated_at": datetime.now().isoformat()
        }

        # Only update allowed fields
        allowed_fields = ["name", "address", "phone", "website", "logo_url"]
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]

        result = (
            supabase.table("organizations")
            .update(update_data)
            .eq("id", org_id)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return jsonify({"success": True, "data": result.data[0]}), 200
        else:
            return jsonify({"success": False, "error": "Organization not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/settings/company", methods=["GET"])
def get_company_settings():
    """Get company settings for the current user's organization"""
    try:
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        supabase = SupabaseClientSingleton.get_instance()

        # Get user's organization
        org_user_result = (
            supabase.table("organization_users")
            .select("organization_id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not org_user_result.data or len(org_user_result.data) == 0:
            # If no organization, return user's basic info
            user_result = supabase.table("users").select("*").eq("id", user_id).single().execute()
            if user_result.data:
                return jsonify({
                    "success": True,
                    "data": {
                        "name": user_result.data.get("name", "My Company"),
                        "address": "",
                        "phone": "",
                        "website": "",
                        "logo_url": None
                    }
                }), 200
            return jsonify({"success": False, "error": "User not found"}), 404

        org_id = org_user_result.data[0]["organization_id"]
        org = org_service.get_by_id(org_id)

        if org:
            return jsonify({
                "success": True,
                "data": {
                    "id": org.id,
                    "name": org.name or "My Company",
                    "address": getattr(org, 'address', '') or "",
                    "phone": getattr(org, 'phone', '') or "",
                    "website": getattr(org, 'website', '') or "",
                    "logo_url": getattr(org, 'logo_url', None)
                }
            }), 200
        else:
            return jsonify({"success": False, "error": "Organization not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/settings/company", methods=["PUT"])
def update_company_settings():
    """Update company settings for the current user's organization"""
    try:
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        supabase = SupabaseClientSingleton.get_instance()
        data = request.json

        # Get user's organization
        org_user_result = (
            supabase.table("organization_users")
            .select("organization_id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not org_user_result.data or len(org_user_result.data) == 0:
            return jsonify({"success": False, "error": "No organization found for user"}), 404

        org_id = org_user_result.data[0]["organization_id"]

        # Prepare update data
        update_data = {
            "updated_at": datetime.now().isoformat()
        }

        # Only update allowed fields
        allowed_fields = ["name", "address", "phone", "website", "logo_url"]
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]

        result = (
            supabase.table("organizations")
            .update(update_data)
            .eq("id", org_id)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return jsonify({"success": True, "data": result.data[0]}), 200
        else:
            return jsonify({"success": False, "error": "Failed to update organization"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/settings/commission-rate", methods=["GET"])
def get_commission_rate():
    """Get the commission rate setting for the current user's organization"""
    try:
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        supabase = SupabaseClientSingleton.get_instance()

        # Get user's organization
        org_user_result = (
            supabase.table("organization_users")
            .select("organization_id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not org_user_result.data or len(org_user_result.data) == 0:
            # Default to 3% if no organization
            return jsonify({
                "success": True,
                "data": {"commission_rate": 0.03}
            }), 200

        org_id = org_user_result.data[0]["organization_id"]

        # Get organization settings
        org_result = (
            supabase.table("organizations")
            .select("commission_rate")
            .eq("id", org_id)
            .single()
            .execute()
        )

        if org_result.data:
            # Default to 3% (0.03) if not set
            commission_rate = org_result.data.get("commission_rate") or 0.03
            return jsonify({
                "success": True,
                "data": {"commission_rate": commission_rate}
            }), 200
        else:
            return jsonify({
                "success": True,
                "data": {"commission_rate": 0.03}
            }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/settings/commission-rate", methods=["PUT"])
def update_commission_rate():
    """Update the commission rate setting for the current user's organization"""
    try:
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        supabase = SupabaseClientSingleton.get_instance()
        data = request.json

        commission_rate = data.get("commission_rate")
        if commission_rate is None:
            return jsonify({"success": False, "error": "commission_rate is required"}), 400

        # Validate commission rate (should be between 0 and 1)
        try:
            commission_rate = float(commission_rate)
            if commission_rate < 0 or commission_rate > 1:
                return jsonify({"success": False, "error": "commission_rate must be between 0 and 1"}), 400
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "commission_rate must be a valid number"}), 400

        # Get user's organization
        org_user_result = (
            supabase.table("organization_users")
            .select("organization_id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not org_user_result.data or len(org_user_result.data) == 0:
            return jsonify({"success": False, "error": "No organization found for user"}), 404

        org_id = org_user_result.data[0]["organization_id"]

        # Update commission rate
        result = (
            supabase.table("organizations")
            .update({
                "commission_rate": commission_rate,
                "updated_at": datetime.now().isoformat()
            })
            .eq("id", org_id)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return jsonify({"success": True, "data": {"commission_rate": commission_rate}}), 200
        else:
            return jsonify({"success": False, "error": "Failed to update commission rate"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/lead-sources", methods=["GET"])
def get_lead_sources():
    try:
        # Get user_id from request
        user_id = request.headers.get('X-User-ID')
        logger.info(f"get_lead_sources called with user_id: {user_id}")
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        # Get lead sources for this user only
        logger.info(f"Fetching lead sources for user_id: {user_id}")
        try:
            lead_sources = lead_source_service.get_all(user_id=user_id)
            logger.info(f"Retrieved {len(lead_sources) if lead_sources else 0} lead sources")
        except Exception as query_error:
            logger.error(f"Database query failed: {query_error}", exc_info=True)
            return jsonify({"success": False, "error": f"Database query failed: {str(query_error)}"}), 500

        # get_all returns a list of dicts directly from Supabase
        lead_source_dicts = lead_sources if lead_sources else []
        
        # Parse JSON fields if they're strings
        for source in lead_source_dicts:
            for field in ["fub_stage_mapping", "options", "metadata", "assignment_rules"]:
                if field in source and isinstance(source[field], str):
                    try:
                        source[field] = json.loads(source[field])
                    except (json.JSONDecodeError, TypeError):
                        # Keep as string if parsing fails
                        pass

        logger.info(f"Returning {len(lead_source_dicts)} lead sources")
        return jsonify({"success": True, "data": lead_source_dicts}), 200
    except Exception as e:
        logger.error(f"Error in get_lead_sources: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/lead-sources/<source_id>", methods=["GET"])
def get_lead_source_by_id(source_id):
    try:
        # Get user_id from request
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        lead_source = lead_source_service.get_by_id(source_id)

        if not lead_source:
            return jsonify({"success": False, "error": "Lead source not found"}), 404

        # Verify ownership
        if hasattr(lead_source, 'user_id') and lead_source.user_id != user_id:
            return jsonify({"success": False, "error": "Access denied"}), 403

        return jsonify({"success": True, "data": lead_source.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/lead-sources/<source_id>/mappings", methods=["PUT"])
def update_lead_source_mappings(source_id):
    try:
        # Get user_id from request
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        data = request.json
        fub_stage_mapping = data.get("fub_stage_mapping")

        if fub_stage_mapping is None:
            return (
                jsonify({"success": False, "error": "fub_stage_mapping is required"}),
                400,
            )

        # Ensure it's a dict (frontend sends dict, but validate)
        if not isinstance(fub_stage_mapping, dict):
            return (
                jsonify({"success": False, "error": "fub_stage_mapping must be an object"}),
                400,
            )

        updated_source = lead_source_service.update_stage_mappings(
            source_id, fub_stage_mapping, user_id
        )

        if not updated_source:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Lead source not found or could not be updated",
                    }
                ),
                404,
            )

        # Convert to dict for response
        if isinstance(updated_source, dict):
            return jsonify({"success": True, "data": updated_source}), 200
        else:
            return jsonify({"success": True, "data": updated_source.to_dict()}), 200
    except Exception as e:
        logger.error(f"Error updating stage mappings: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/lead-sources/<source_id>/status", methods=["PATCH"])
def update_lead_source_status(source_id):
    """Update is_active status for a lead source"""
    try:
        # Get user_id from request
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        data = request.json
        is_active = data.get("is_active")

        if is_active is None:
            return (
                jsonify({"success": False, "error": "is_active is required"}),
                400,
            )

        # Update status using service method (ownership verification happens in service)
        updated_source = lead_source_service.toggle_source_active_status(source_id, is_active, user_id)
        
        if not updated_source:
            return (
                jsonify({"success": False, "error": "Could not update status"}),
                500,
            )

        # Return updated source
        if isinstance(updated_source, dict):
            return jsonify({"success": True, "data": serialize_for_json(updated_source)}), 200
        else:
            return jsonify({"success": True, "data": serialize_for_json(updated_source.to_dict())}), 200

    except Exception as e:
        logger.error(f"Error updating lead source status: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/lead-sources/<source_id>/sync-settings", methods=["PATCH"])
def update_lead_source_sync_settings(source_id):
    """Update scheduled sync interval for a lead source"""
    try:
        # Get user_id from request
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        data = request.json or {}
        raw_interval = data.get("sync_interval_days")

        sync_interval_days = None

        if isinstance(raw_interval, str):
            normalized = raw_interval.strip().lower()
            if normalized not in ("", "none", "never"):
                try:
                    sync_interval_days = int(raw_interval)
                except ValueError:
                    return (
                        jsonify({
                            "success": False,
                            "error": "sync_interval_days must be one of [1, 3, 7, 14, 21, 30, 45, 60] or 'never'",
                        }),
                        400,
                    )
        elif raw_interval is not None:
            try:
                sync_interval_days = int(raw_interval)
            except (TypeError, ValueError):
                return (
                    jsonify({
                        "success": False,
                        "error": "sync_interval_days must be an integer number of days or null",
                    }),
                    400,
                )

        if sync_interval_days == 0:
            sync_interval_days = None

        try:
            updated_source = lead_source_service.update_sync_settings(
                source_id, sync_interval_days, user_id
            )
        except ValueError as validation_error:
            return (
                jsonify({"success": False, "error": str(validation_error)}),
                400,
            )

        if not updated_source:
            return (
                jsonify({"success": False, "error": "Lead source not found"}),
                404,
            )

        updated_dict = (
            updated_source
            if isinstance(updated_source, dict)
            else updated_source.to_dict()
        )

        return jsonify({"success": True, "data": updated_dict}), 200

    except Exception as e:  # noqa: BLE001
        logger.error(f"Error updating lead source sync settings: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/lead-sources/<source_id>/credentials", methods=["PUT"])
def update_lead_source_credentials(source_id):
    """Update credentials for a lead source (stored in metadata.credentials)"""
    try:
        data = request.json
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return (
                jsonify({"success": False, "error": "email and password are required"}),
                400,
            )

        # Get existing source to preserve other metadata
        source = lead_source_service.get_by_id(source_id)
        if not source:
            return (
                jsonify({"success": False, "error": "Lead source not found"}),
                404,
            )

        # Get existing metadata or create new
        if isinstance(source, dict):
            existing_metadata = source.get("metadata", {}) or {}
        else:
            existing_metadata = source.metadata if hasattr(source, 'metadata') and source.metadata else {}

        # Ensure metadata is a dict
        if isinstance(existing_metadata, str):
            import json
            try:
                existing_metadata = json.loads(existing_metadata)
            except:
                existing_metadata = {}

        # Update credentials in metadata
        if not isinstance(existing_metadata, dict):
            existing_metadata = {}

        existing_metadata["credentials"] = {
            "email": email,
            "password": password
        }

        # Update the source with new metadata
        supabase = SupabaseClientSingleton.get_instance()
        import json as json_lib
        metadata_json = json_lib.dumps(existing_metadata)

        result = (
            supabase.table("lead_source_settings")
            .update({"metadata": metadata_json, "updated_at": "now()"})
            .eq("id", source_id)
            .execute()
        )

        if not result.data or len(result.data) == 0:
            return (
                jsonify({"success": False, "error": "Could not update credentials"}),
                500,
            )

        # Return updated source
        updated_source = lead_source_service.get_by_id(source_id)
        if isinstance(updated_source, dict):
            return jsonify({"success": True, "data": updated_source}), 200
        else:
            return jsonify({"success": True, "data": updated_source.to_dict()}), 200

    except Exception as e:
        logger.error(f"Error updating credentials: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/lead-sources/<source_id>/ai-update-settings", methods=["GET", "PUT"])
def manage_ai_update_settings(source_id):
    """
    Get or update AI update note settings for a lead source.

    Settings are stored in metadata.ai_update_settings:
    - enabled: bool - Enable/disable AI-generated updates
    - mode: str - 'fallback' (only when no @update), 'always', 'supplement'
    - save_to_fub: bool - Save generated update as FUB note for audit trail
    - context_sources: list - What context to include ['messages', 'notes', 'timeline']
    - tone: str - 'professional', 'concise', 'detailed'
    - max_length: int - Maximum length of generated update
    """
    try:
        # Get existing source
        source = lead_source_service.get_by_id(source_id)
        if not source:
            return jsonify({"success": False, "error": "Lead source not found"}), 404

        # Get existing metadata
        if isinstance(source, dict):
            existing_metadata = source.get("metadata", {}) or {}
        else:
            existing_metadata = source.metadata if hasattr(source, 'metadata') and source.metadata else {}

        if isinstance(existing_metadata, str):
            try:
                existing_metadata = json.loads(existing_metadata)
            except (json.JSONDecodeError, TypeError):
                existing_metadata = {}

        if request.method == "GET":
            # Return current AI update settings
            ai_settings = existing_metadata.get("ai_update_settings", {
                "enabled": False,
                "mode": "fallback",
                "save_to_fub": True,
                "context_sources": ["messages", "notes"],
                "tone": "professional",
                "max_length": 300
            })
            return jsonify({"success": True, "data": ai_settings}), 200

        # PUT - Update settings
        data = request.json

        # Validate settings
        valid_modes = ["fallback", "always", "supplement"]
        valid_tones = ["professional", "concise", "detailed"]
        valid_contexts = ["messages", "notes", "timeline", "all"]

        if data.get("mode") and data["mode"] not in valid_modes:
            return jsonify({"success": False, "error": f"Invalid mode. Must be one of: {valid_modes}"}), 400

        if data.get("tone") and data["tone"] not in valid_tones:
            return jsonify({"success": False, "error": f"Invalid tone. Must be one of: {valid_tones}"}), 400

        if data.get("context_sources"):
            invalid = [c for c in data["context_sources"] if c not in valid_contexts]
            if invalid:
                return jsonify({"success": False, "error": f"Invalid context sources: {invalid}. Must be from: {valid_contexts}"}), 400

        # Build AI settings
        ai_settings = existing_metadata.get("ai_update_settings", {})
        if "enabled" in data:
            ai_settings["enabled"] = bool(data["enabled"])
        if "mode" in data:
            ai_settings["mode"] = data["mode"]
        if "save_to_fub" in data:
            ai_settings["save_to_fub"] = bool(data["save_to_fub"])
        if "context_sources" in data:
            ai_settings["context_sources"] = data["context_sources"]
        if "tone" in data:
            ai_settings["tone"] = data["tone"]
        if "max_length" in data:
            ai_settings["max_length"] = min(500, max(50, int(data["max_length"])))

        # Update metadata
        existing_metadata["ai_update_settings"] = ai_settings

        # Save to database
        result = (
            supabase.table("lead_source_settings")
            .update({"metadata": existing_metadata})
            .eq("id", source_id)
            .execute()
        )

        if not result.data or len(result.data) == 0:
            return jsonify({"success": False, "error": "Could not update AI settings"}), 500

        logger.info(f"Updated AI update settings for source {source_id}: enabled={ai_settings.get('enabled')}, mode={ai_settings.get('mode')}")

        return jsonify({"success": True, "data": ai_settings}), 200

    except Exception as e:
        logger.error(f"Error managing AI update settings: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# FUB Stages
@supabase_api.route("/fub-stages", methods=["GET"])
def get_fub_stages():
    """Get all FUB stages for stage mapping configuration"""
    try:
        from app.service.stage_mapper_service import StageMapperService
        from app.service.fub_api_key_service import FUBAPIKeyServiceSingleton
        from flask import g

        # Get user ID from request header
        user_id = request.headers.get('X-User-ID')

        # Try to get user-specific API key
        user_api_key = None
        if user_id:
            try:
                fub_service = FUBAPIKeyServiceSingleton.get_instance()
                user_api_key = fub_service.get_api_key_for_user(user_id)
                if user_api_key:
                    logger.info(f"Using FUB API key for user {user_id}")
                else:
                    logger.warning(f"No FUB API key found for user {user_id}, falling back to env key")
            except Exception as e:
                logger.warning(f"Error getting user API key: {e}")
        else:
            logger.warning("No X-User-ID header provided, using fallback API key")

        # Fall back to environment API key if no user key found
        if not user_api_key:
            from app.utils.constants import Credentials
            creds = Credentials()
            user_api_key = creds.FUB_API_KEY
            logger.info("Using environment FUB_API_KEY as fallback")

        stage_mapper = StageMapperService(user_api_key=user_api_key)
        stages = stage_mapper.get_fub_stages(force_refresh=True)

        logger.info(f"Fetched {len(stages)} FUB stages from FUB API")

        # Format stages for frontend - include all stages, no filtering
        formatted_stages = [
            {
                "id": str(stage.get("id", "")),
                "name": stage.get("name", ""),
            }
            for stage in stages
        ]

        # Log all stage names for debugging
        stage_names = [s["name"] for s in formatted_stages]
        logger.info(f"FUB stages available for mapping: {stage_names}")

        return jsonify({"success": True, "data": formatted_stages}), 200
    except Exception as e:
        logger.error(f"Error fetching FUB stages: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# Notifications
@supabase_api.route("/settings/notifications", methods=["GET"])
def get_notification_settings():
    try:
        # Get organization ID from request header, or look it up from user ID
        org_id = request.headers.get("X-Organization-ID")
        user_id = request.headers.get("X-User-ID")

        if not org_id and user_id:
            org_id = get_org_id_for_user(user_id)

        logger.info(f"Getting notification settings for organization ID: {org_id}")

        if not org_id:
            # Return default settings if no organization
            logger.info("No organization, returning default notification settings")
            return (
                jsonify(
                    {
                        "success": True,
                        "data": {
                            "new-lead_email": True,
                            "new-lead_sms": True,
                            "new-lead_push": False,
                            "new-lead_slack": False,
                            "stage-update_email": True,
                            "stage-update_sms": False,
                            "stage-update_push": False,
                            "stage-update_slack": False,
                            "commission_email": True,
                            "commission_sms": False,
                            "commission_push": False,
                            "commission_slack": False,
                        },
                    }
                ),
                200,
            )

        # Get user ID from request header (optional)
        user_id = request.headers.get("X-User-ID")
        logger.info(f"User ID in request (optional): {user_id}")

        # Get notification settings
        settings = notification_settings_service.get_by_organization(org_id, user_id)
        logger.info(f"Retrieved settings: {settings}")

        if not settings:
            logger.info("No settings found, returning default settings")
            return (
                jsonify(
                    {
                        "success": True,
                        "data": {
                            "settings": {
                                "new-lead": {
                                    "email": True,
                                    "sms": True,
                                    "push": False,
                                    "slack": False,
                                },
                                "stage-update": {
                                    "email": True,
                                    "sms": False,
                                    "push": False,
                                    "slack": False,
                                },
                                "commission": {
                                    "email": True,
                                    "sms": False,
                                    "push": False,
                                    "slack": False,
                                },
                            }
                        },
                    }
                ),
                200,
            )

        logger.info(f"Returning settings: {settings.settings}")
        return jsonify({"success": True, "data": {"settings": settings.settings}}), 200
    except Exception as e:
        logger.error(f"Error getting notification settings: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/settings/notifications", methods=["PUT"])
def update_notification_settings():
    try:
        # Get organization ID from request header, or look it up from user ID
        org_id = request.headers.get("X-Organization-ID")
        user_id = request.headers.get("X-User-ID")

        if not org_id and user_id:
            org_id = get_org_id_for_user(user_id)

        logger.info(f"Updating notification settings for organization ID: {org_id}")

        if not org_id:
            # No organization yet - just acknowledge the save (settings stored locally in browser)
            logger.info("No organization, acknowledging save request")
            return jsonify({"success": True, "message": "Settings saved locally"}), 200

        logger.info(f"User ID in request: {user_id}")

        # Get data from request
        data = request.json
        logger.info(f"Request data: {data}")

        notification_settings = data.get("settings")
        logger.info(f"Notification settings to update: {notification_settings}")

        if not notification_settings:
            logger.warning("Missing settings in request body")
            return jsonify({"success": False, "error": "Settings are required"}), 400

        # Get existing settings
        settings = notification_settings_service.get_by_organization(org_id, user_id)
        logger.info(f"Existing settings: {settings}")

        if not settings:
            # Create new settings if they don't exist
            logger.info("No existing settings found, creating default settings")
            settings = notification_settings_service.create_default_settings(
                org_id, user_id
            )
            logger.info(f"Created default settings: {settings}")

        # Update settings
        logger.info("Updating settings with new values")
        settings.settings = notification_settings
        settings.updated_at = datetime.now()

        # Save settings
        logger.info("Saving updated settings to database")
        updated_settings = notification_settings_service.update(settings)
        logger.info(f"Updated settings result: {updated_settings}")

        if not updated_settings:
            logger.error("Failed to update notification settings")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Failed to update notification settings",
                    }
                ),
                500,
            )

        logger.info(f"Successfully updated settings: {updated_settings.settings}")
        return (
            jsonify({"success": True, "data": {"settings": updated_settings.settings}}),
            200,
        )
    except Exception as e:
        logger.error(f"Error updating notification settings: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# Team Members
@supabase_api.route("/team-members", methods=["GET"])
def get_team_members():
    try:
        # Get organization ID from request header, or look it up from user ID
        org_id = request.headers.get("X-Organization-ID")

        if not org_id:
            # Try to get organization from user ID
            user_id = request.headers.get("X-User-ID")
            if user_id:
                org_id = get_org_id_for_user(user_id)

        if not org_id:
            # Return empty array if no organization (user not part of any org yet)
            return jsonify({"success": True, "data": []}), 200

        # Get team members
        team_members = team_member_service.get_by_organization(org_id)

        # Convert to dictionaries
        team_member_dicts = [member.to_dict() for member in team_members]

        return jsonify({"success": True, "data": team_member_dicts}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/team-members/<member_id>", methods=["GET"])
def get_team_member(member_id):
    try:
        team_member = team_member_service.get_by_id(member_id)

        if not team_member:
            return jsonify({"success": False, "error": "Team member not found"}), 404

        return jsonify({"success": True, "data": team_member.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/team-members", methods=["POST"])
def create_team_member():
    try:
        data = request.json

        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return (
                jsonify({"success": False, "error": "Organization ID is required"}),
                400,
            )

        # Create team member
        new_team_member = team_member_service.create(org_id, data)

        if not new_team_member:
            return (
                jsonify({"success": False, "error": "Failed to create team member"}),
                500,
            )

        return jsonify({"success": True, "data": new_team_member.to_dict()}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/team-members/<member_id>", methods=["PUT"])
def update_team_member(member_id):
    try:
        data = request.json
        updated_team_member = team_member_service.update(member_id, data)

        if not updated_team_member:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Team member not found or could not be updated",
                    }
                ),
                404,
            )

        return jsonify({"success": True, "data": updated_team_member.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/team-members/<member_id>", methods=["DELETE"])
def delete_team_member(member_id):
    try:
        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return (
                jsonify({"success": False, "error": "Organization ID is required"}),
                400,
            )

        # Delete team member
        success = team_member_service.delete(org_id, member_id)

        if not success:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Team member not found or could not be deleted",
                    }
                ),
                404,
            )

        return jsonify({"success": True, "data": {"id": member_id}}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/team-members/<member_id>/role", methods=["PUT"])
def update_team_member_role(member_id):
    try:
        data = request.json
        role = data.get("role")

        if not role:
            return jsonify({"success": False, "error": "Role is required"}), 400

        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return (
                jsonify({"success": False, "error": "Organization ID is required"}),
                400,
            )

        # Update role
        updated_team_member = team_member_service.update_role(org_id, member_id, role)

        if not updated_team_member:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Team member not found or could not be updated",
                    }
                ),
                404,
            )

        return jsonify({"success": True, "data": updated_team_member.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/team-members/<member_id>/notifications", methods=["PUT"])
def update_team_member_notifications(member_id):
    try:
        data = request.json
        updates = {}

        if "email_notifications" in data:
            updates["email_notifications"] = data["email_notifications"]

        if "sms_notifications" in data:
            updates["sms_notifications"] = data["sms_notifications"]

        if not updates:
            return (
                jsonify(
                    {"success": False, "error": "No notification preferences provided"}
                ),
                400,
            )

        # Update notifications
        updated_team_member = team_member_service.update(member_id, updates)

        if not updated_team_member:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Team member not found or could not be updated",
                    }
                ),
                404,
            )

        return jsonify({"success": True, "data": updated_team_member.to_dict()}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/team-members/invite", methods=["POST"])
def invite_team_member():
    try:
        data = request.json
        email = data.get("email")
        role = data.get("role", "agent")

        if not email:
            return jsonify({"success": False, "error": "Email is required"}), 400

        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return (
                jsonify({"success": False, "error": "Organization ID is required"}),
                400,
            )

        # Invite team member
        result = team_member_service.invite(org_id, email, role)

        if not result:
            return (
                jsonify({"success": False, "error": "Failed to invite team member"}),
                500,
            )

        return jsonify({"success": True, "data": result}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/team-members/resend-invite", methods=["POST"])
def resend_team_invitation():
    try:
        data = request.json
        email = data.get("email")

        if not email:
            return jsonify({"success": False, "error": "Email is required"}), 400

        # Resend invitation
        result = team_member_service.resend_invite(email)

        if not result:
            return jsonify({"success": False, "error": "User not found"}), 404

        return jsonify({"success": True, "data": result}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/team-members/magic-link-invite", methods=["POST"])
def create_magic_link_invitation():
    """Create a pending invitation record for magic link flow"""
    try:
        data = request.json
        email = data.get("email")
        role = data.get("role", "agent")
        inviter_name = data.get("inviter_name", "Team Admin")

        if not email:
            return jsonify({"success": False, "error": "Email is required"}), 400

        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return (
                jsonify({"success": False, "error": "Organization ID is required"}),
                400,
            )

        # Get organization details for the invitation
        org_result = org_service.get_by_id(org_id)
        if not org_result:
            return jsonify({"success": False, "error": "Organization not found"}), 404

        # Create pending invitation record using team member service
        result = team_member_service.create_magic_link_invitation(
            org_id, email, role, inviter_name, org_result.name
        )

        if not result:
            return (
                jsonify({"success": False, "error": "Failed to create invitation"}),
                500,
            )

        return jsonify({
            "success": True, 
            "data": result,
            "message": "Invitation record created successfully"
        }), 201
    except Exception as e:
        logger.error(f"Error creating magic link invitation: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/team-members/complete-magic-link-invitation", methods=["POST"])
def complete_magic_link_invitation():
    """Complete the magic link invitation process"""
    try:
        # Get user ID from token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return (
                jsonify({"success": False, "error": "Invalid authorization header"}),
                401,
            )

        token = auth_header.split(" ")[1]

        # Use Supabase client to verify token and get user info
        supabase = SupabaseClientSingleton.get_instance()
        try:
            user_response = supabase.auth.get_user(token)
            user_id = user_response.user.id
            user_email = user_response.user.email
            user_metadata = user_response.user.user_metadata or {}
        except Exception as auth_error:
            logger.error(f"Token verification error: {str(auth_error)}")
            return jsonify({"success": False, "error": "Invalid or expired token"}), 401

        # Get completion data from request
        data = request.json
        full_name = data.get("full_name")
        first_name = data.get("first_name")
        last_name = data.get("last_name")

        if not full_name and not (first_name and last_name):
            return jsonify({
                "success": False, 
                "error": "Name information is required"
            }), 400

        # Extract invitation metadata
        organization_id = user_metadata.get("organization_id")
        role = user_metadata.get("role", "agent")
        
        if not organization_id:
            return jsonify({
                "success": False, 
                "error": "Invalid invitation - missing organization information"
            }), 400

        # Complete the invitation using team member service
        result = team_member_service.complete_magic_link_invitation(
            user_id=user_id,
            email=user_email,
            organization_id=organization_id,
            role=role,
            full_name=full_name,
            first_name=first_name,
            last_name=last_name
        )

        if not result:
            return (
                jsonify({"success": False, "error": "Failed to complete invitation"}),
                500,
            )

        return jsonify({
            "success": True, 
            "data": result,
            "message": "Invitation completed successfully"
        }), 200

    except Exception as e:
        logger.error(f"Error completing magic link invitation: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/team-members/pending-invitations", methods=["GET"])
def get_pending_invitations():
    """Get pending invitations for an organization"""
    try:
        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return (
                jsonify({"success": False, "error": "Organization ID is required"}),
                400,
            )

        # Get pending invitations
        result = (
            SupabaseClientSingleton.get_instance()
            .table("pending_invitations")
            .select("*")
            .eq("organization_id", org_id)
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute()
        )

        invitations = result.data or []
        
        return jsonify({
            "success": True, 
            "data": invitations,
            "count": len(invitations)
        }), 200

    except Exception as e:
        logger.error(f"Error getting pending invitations: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/team-members/invitation-status/<email>", methods=["GET"])
def get_invitation_status():
    """Get invitation status for a specific email"""
    try:
        # Get the email from URL parameter
        email = request.view_args.get('email')
        if not email:
            return jsonify({"success": False, "error": "Email is required"}), 400

        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return (
                jsonify({"success": False, "error": "Organization ID is required"}),
                400,
            )

        # Check invitation status
        result = (
            SupabaseClientSingleton.get_instance()
            .table("pending_invitations")
            .select("*")
            .eq("email", email)
            .eq("organization_id", org_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if result.data and len(result.data) > 0:
            invitation = result.data[0]
            return jsonify({
                "success": True,
                "data": {
                    "email": email,
                    "status": invitation.get("status"),
                    "role": invitation.get("role"),
                    "created_at": invitation.get("created_at"),
                    "expires_at": invitation.get("expires_at"),
                    "has_pending_invitation": invitation.get("status") == "pending"
                }
            }), 200
        else:
            return jsonify({
                "success": True,
                "data": {
                    "email": email,
                    "status": "not_found",
                    "has_pending_invitation": False
                }
            }), 200

    except Exception as e:
        logger.error(f"Error getting invitation status: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/team-members/sync-from-fub", methods=["POST"])
def sync_team_members_from_fub():
    """
    Sync team members from Follow Up Boss.
    This fetches all users from FUB and returns them for the frontend to display.
    The frontend can then choose which users to invite.
    """
    try:
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        # Get FUB API key from system settings (global settings)
        settings = system_settings_service.get()
        fub_api_key = settings.fub_api_key if settings else None

        if not fub_api_key:
            return jsonify({
                "success": False,
                "error": "FUB API key not configured. Please set it in System Settings."
            }), 400

        # Initialize FUB client and get users
        from app.database.fub_api_client import FUBApiClient
        fub_client = FUBApiClient(api_key=fub_api_key)
        fub_users = fub_client.get_users()

        if not fub_users:
            return jsonify({
                "success": True,
                "data": [],
                "message": "No team members found in Follow Up Boss"
            }), 200

        # Format the users for the frontend
        formatted_users = []
        for user in fub_users:
            formatted_users.append({
                "fub_id": user.get("id"),
                "name": user.get("name", ""),
                "email": user.get("email", ""),
                "role": user.get("role", "agent"),
                "phone": user.get("phones", [{}])[0].get("value", "") if user.get("phones") else "",
                "active": user.get("active", True),
            })

        return jsonify({
            "success": True,
            "data": formatted_users,
            "count": len(formatted_users)
        }), 200

    except Exception as e:
        logger.error(f"Error syncing team members from FUB: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/proxy/configuration", methods=["GET"])
def get_proxy_configuration():
    """Get proxy configuration for the current organization"""
    try:
        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return (
                jsonify({"success": False, "error": "Organization ID is required"}),
                400,
            )

        from app.service.proxy_service import ProxyServiceSingleton
        
        proxy_service = ProxyServiceSingleton.get_instance()
        config = proxy_service.get_organization_proxy_config(org_id)
        
        if config:
            # Remove sensitive information from response
            safe_config = {
                "proxy_host": config.get("proxy_host"),
                "http_port": config.get("http_port"),
                "socks5_port": config.get("socks5_port"),
                "proxy_type": config.get("proxy_type"),
                "rotation_enabled": config.get("rotation_enabled"),
                "session_duration": config.get("session_duration"),
                "has_configuration": True
            }
            return jsonify({"success": True, "data": safe_config}), 200
        else:
            return jsonify({
                "success": True, 
                "data": {"has_configuration": False}
            }), 200

    except Exception as e:
        logger.error(f"Error getting proxy configuration: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/proxy/configuration", methods=["POST"])
def create_proxy_configuration():
    """Create or update proxy configuration for the current organization"""
    try:
        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return (
                jsonify({"success": False, "error": "Organization ID is required"}),
                400,
            )

        # Get configuration data from request
        data = request.json
        proxy_username = data.get("proxy_username")
        proxy_password = data.get("proxy_password")
        proxy_host = data.get("proxy_host")
        proxy_type = data.get("proxy_type", "http")
        rotation_enabled = data.get("rotation_enabled", True)
        session_duration = data.get("session_duration", "10m")

        if not proxy_username or not proxy_password:
            return jsonify({
                "success": False, 
                "error": "Proxy username and password are required"
            }), 400

        from app.service.proxy_service import ProxyServiceSingleton
        
        proxy_service = ProxyServiceSingleton.get_instance()
        success = proxy_service.create_organization_proxy_config(
            organization_id=org_id,
            proxy_username=proxy_username,
            proxy_password=proxy_password,
            proxy_host=proxy_host,
            proxy_type=proxy_type,
            rotation_enabled=rotation_enabled,
            session_duration=session_duration
        )

        if success:
            return jsonify({
                "success": True, 
                "message": "Proxy configuration saved successfully"
            }), 201
        else:
            return jsonify({
                "success": False, 
                "error": "Failed to save proxy configuration"
            }), 500

    except Exception as e:
        logger.error(f"Error creating proxy configuration: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/proxy/test", methods=["POST"])
def test_proxy_connection():
    """Test proxy connection for the current organization"""
    try:
        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return (
                jsonify({"success": False, "error": "Organization ID is required"}),
                400,
            )

        from app.service.proxy_service import ProxyServiceSingleton
        
        proxy_service = ProxyServiceSingleton.get_instance()
        test_result = proxy_service.test_proxy_connection(org_id)

        if test_result:
            return jsonify({
                "success": True, 
                "message": "Proxy connection test successful"
            }), 200
        else:
            return jsonify({
                "success": False, 
                "error": "Proxy connection test failed"
            }), 400

    except Exception as e:
        logger.error(f"Error testing proxy connection: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# System Settings
@supabase_api.route("/system-settings", methods=["GET"])
def get_system_settings():
    try:
        # Get system settings
        settings = system_settings_service.get()

        return jsonify({"success": True, "data": serialize_for_json(settings.to_dict())}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/system-settings", methods=["PUT"])
def update_system_settings():
    try:
        data = request.json

        # Update system settings
        updated_settings = system_settings_service.update(data)

        if not updated_settings:
            return (
                jsonify(
                    {"success": False, "error": "Failed to update system settings"}
                ),
                500,
            )

        return jsonify({"success": True, "data": serialize_for_json(updated_settings.to_dict())}), 200
    except Exception as e:
        logger.error(f"Error updating system settings: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/system-settings/api-key", methods=["PUT"])
def update_api_key():
    try:
        data = request.json
        api_key = data.get("fub_api_key")

        if not api_key:
            return jsonify({"success": False, "error": "API key is required"}), 400

        # Update API key
        success = system_settings_service.update_api_key(api_key)

        if not success:
            return jsonify({"success": False, "error": "Failed to update API key"}), 500

        return jsonify({"success": True, "data": {"fub_api_key_set": True}}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Profile
@supabase_api.route("/users/current/profile", methods=["GET"])
def get_current_user_profile():
    try:
        # Get user ID from token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return (
                jsonify({"success": False, "error": "Invalid authorization header"}),
                401,
            )

        token = auth_header.split(" ")[1]

        # Use Supabase client to verify token and get user ID
        supabase = SupabaseClientSingleton.get_instance()
        try:
            # Get user from token
            user_response = supabase.auth.get_user(token)
            user_id = user_response.user.id
        except Exception as auth_error:
            print(f"Token verification error: {str(auth_error)}")
            return jsonify({"success": False, "error": "Invalid or expired token"}), 401

        # Get profile using the existing user service method
        profile = user_service.get_profile(user_id)

        # If profile doesn't exist, create one
        if not profile:
            # Get user data first
            user = user_service.get_by_id(user_id)
            if not user:
                return jsonify({"success": False, "error": "User not found"}), 404

            # Create profile using the existing model and service
            profile = UserProfile()
            profile.id = user_id
            profile.email = user.email
            profile.full_name = user.full_name
            profile.phone_number = user.phone_number
            profile.role = user.role
            profile.email_notifications = user.email_notifications
            profile.sms_notifications = user.sms_notifications
            # Set default onboarding status for new profiles
            profile.onboarding_completed = False
            profile.fub_api_key = None

            # Create the profile using the existing service method
            profile = user_service.create_profile(profile)

        return jsonify({"success": True, "data": profile.to_dict()}), 200
    except Exception as e:
        print(f"Error in get_current_user_profile: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/users/current/profile", methods=["PUT"])
def update_current_user_profile():
    try:
        # Get user ID from token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return (
                jsonify({"success": False, "error": "Invalid authorization header"}),
                401,
            )

        token = auth_header.split(" ")[1]

        # Use Supabase client to verify token and get user ID
        supabase = SupabaseClientSingleton.get_instance()
        try:
            # Get user from token
            user_response = supabase.auth.get_user(token)
            user_id = user_response.user.id
        except Exception as auth_error:
            print(f"Token verification error: {str(auth_error)}")
            return jsonify({"success": False, "error": "Invalid or expired token"}), 401

        # Get data from request
        data = request.json

        # Get existing profile
        profile = user_service.get_profile(user_id)

        if not profile:
            return jsonify({"success": False, "error": "Profile not found"}), 404

        # Update profile fields
        for key, value in data.items():
            if hasattr(profile, key):
                setattr(profile, key, value)

        # Save updated profile using the existing service method
        updated_profile = user_service.update_profile(profile)

        return jsonify({"success": True, "data": updated_profile.to_dict()}), 200
    except Exception as e:
        print(f"Error in update_current_user_profile: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/users/current/profile/api-key", methods=["PUT"])
def update_current_user_api_key():
    try:
        # Get user ID from token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return (
                jsonify({"success": False, "error": "Invalid authorization header"}),
                401,
            )

        token = auth_header.split(" ")[1]

        # Use Supabase client to verify token and get user ID
        supabase = SupabaseClientSingleton.get_instance()
        try:
            # Get user from token
            user_response = supabase.auth.get_user(token)
            user_id = user_response.user.id
        except Exception as auth_error:
            print(f"Token verification error: {str(auth_error)}")
            return jsonify({"success": False, "error": "Invalid or expired token"}), 401

        # Get data from request
        data = request.json
        api_key = data.get("fub_api_key")

        if not api_key:
            return jsonify({"success": False, "error": "API key is required"}), 400

        # Use the FUB API key service to store the key
        from app.service.fub_api_key_service import FUBAPIKeyServiceSingleton

        fub_service = FUBAPIKeyServiceSingleton.get_instance()

        # Use synchronous method to store the API key directly
        # This avoids async/event loop issues in Flask
        success = fub_service.store_api_key_sync(user_id, api_key)

        if not success:
            return jsonify({
                "success": False,
                "error": "Failed to save API key. Please try again."
            }), 500

        return jsonify({"success": True, "data": {"fub_api_key_set": True}}), 200
    except Exception as e:
        print(f"Error in update_current_user_api_key: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/users/current/profile/complete-onboarding", methods=["POST"])
def complete_onboarding():
    """Mark user onboarding as completed"""
    try:
        # Get user ID from token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return (
                jsonify({"success": False, "error": "Invalid authorization header"}),
                401,
            )

        token = auth_header.split(" ")[1]

        # Use Supabase client to verify token and get user ID
        supabase = SupabaseClientSingleton.get_instance()
        try:
            # Get user from token
            user_response = supabase.auth.get_user(token)
            user_id = user_response.user.id
        except Exception as auth_error:
            print(f"Token verification error: {str(auth_error)}")
            return jsonify({"success": False, "error": "Invalid or expired token"}), 401

        # Get existing profile
        profile = user_service.get_profile(user_id)

        if not profile:
            return jsonify({"success": False, "error": "Profile not found"}), 404

        # Check if user has FUB API key
        if not profile.fub_api_key:
            return jsonify({
                "success": False, 
                "error": "Cannot complete onboarding without FUB API key"
            }), 400

        # Mark onboarding as completed
        profile.onboarding_completed = True
        updated_profile = user_service.update_profile(profile)

        return jsonify({
            "success": True, 
            "data": {
                "onboarding_completed": True,
                "message": "Onboarding completed successfully"
            }
        }), 200
    except Exception as e:
        print(f"Error in complete_onboarding: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# Subscription
# Subscription endpoints
@supabase_api.route("/subscription", methods=["GET"])
def get_subscription():
    try:
        # Add comprehensive logging
        logger.info("🔍 Processing GET /subscription request")
        logger.info(f"📋 Request headers: {dict(request.headers)}")
        logger.info(f"🌐 Request method: {request.method}")
        logger.info(f"📍 Request URL: {request.url}")

        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        logger.info(f"🏢 Organization ID from header: '{org_id}'")

        if not org_id:
            logger.error("❌ Missing X-Organization-ID header")
            logger.error(f"❌ Available headers: {list(request.headers.keys())}")
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Organization ID is required",
                        "debug_info": {
                            "headers_received": dict(request.headers),
                            "missing_header": "X-Organization-ID",
                            "available_headers": list(request.headers.keys()),
                        },
                    }
                ),
                400,
            )

        logger.info(f"🔍 Fetching subscription for organization: {org_id}")
        subscription = subscription_service.get_subscription(org_id)
        logger.info(f"✅ Successfully retrieved subscription data for org {org_id}")

        return jsonify({"success": True, "data": subscription}), 200
    except Exception as e:
        logger.error(f"❌ Error in get_subscription: {str(e)}")
        logger.error(f"❌ Exception type: {type(e).__name__}")
        import traceback

        logger.error(f"❌ Full traceback: {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/subscription/cancel", methods=["POST"])
def cancel_subscription():
    try:
        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return (
                jsonify({"success": False, "error": "Organization ID is required"}),
                400,
            )

        success = subscription_service.cancel_subscription(org_id)

        if not success:
            return (
                jsonify({"success": False, "error": "Failed to cancel subscription"}),
                500,
            )

        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/subscription/reactivate", methods=["POST"])
def reactivate_subscription():
    try:
        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return (
                jsonify({"success": False, "error": "Organization ID is required"}),
                400,
            )

        success = subscription_service.reactivate_subscription(org_id)

        if not success:
            return (
                jsonify(
                    {"success": False, "error": "Failed to reactivate subscription"}
                ),
                500,
            )

        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Payment method endpoints
@supabase_api.route("/payment-methods", methods=["GET"])
def get_payment_methods():
    try:
        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return (
                jsonify({"success": False, "error": "Organization ID is required"}),
                400,
            )

        payment_methods = subscription_service.get_payment_methods(org_id)

        return jsonify({"success": True, "data": payment_methods}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/payment-methods", methods=["POST"])
def add_payment_method():
    try:
        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return (
                jsonify({"success": False, "error": "Organization ID is required"}),
                400,
            )

        # Get data from request
        data = request.json
        payment_method_id = data.get("paymentMethodId")

        if not payment_method_id:
            return (
                jsonify({"success": False, "error": "Payment method ID is required"}),
                400,
            )

        payment_method = subscription_service.add_payment_method(
            org_id, payment_method_id
        )

        return jsonify({"success": True, "data": payment_method}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/payment-methods/<payment_method_id>/default", methods=["POST"])
def set_default_payment_method(payment_method_id):
    try:
        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return (
                jsonify({"success": False, "error": "Organization ID is required"}),
                400,
            )

        success = subscription_service.set_default_payment_method(
            org_id, payment_method_id
        )

        if not success:
            return (
                jsonify(
                    {"success": False, "error": "Failed to set default payment method"}
                ),
                500,
            )

        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/payment-methods/<payment_method_id>", methods=["DELETE"])
def delete_payment_method(payment_method_id):
    try:
        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return (
                jsonify({"success": False, "error": "Organization ID is required"}),
                400,
            )

        success = subscription_service.delete_payment_method(org_id, payment_method_id)

        if not success:
            return (
                jsonify({"success": False, "error": "Failed to delete payment method"}),
                500,
            )

        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Billing history endpoints
@supabase_api.route("/billing-history", methods=["GET"])
def get_billing_history():
    try:
        # Get organization ID from request header
        org_id = request.headers.get("X-Organization-ID")
        if not org_id:
            return (
                jsonify({"success": False, "error": "Organization ID is required"}),
                400,
            )

        billing_history = subscription_service.get_billing_history(org_id)

        return jsonify({"success": True, "data": billing_history}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Helper function to get organization ID from user ID
def get_org_id_for_user(user_id: str):
    """Look up the organization ID for a given user ID"""
    supabase = SupabaseClientSingleton.get_instance()
    result = (
        supabase.table("organization_users")
        .select("organization_id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if result.data and len(result.data) > 0:
        return result.data[0]["organization_id"]
    return None


# ===========================================
# MODULAR PRICING CONFIGURATION
# Matches frontend lib/plans.ts
# ===========================================

# BASE PLATFORM SUBSCRIPTIONS (Lead source syncing)
# NO team member limits - all plans have unlimited team members
BASE_PLAN_LIMITS = {
    "starter": {"leadSources": 1, "teamMembers": -1},
    "growth": {"leadSources": 3, "teamMembers": -1},
    "pro": {"leadSources": 5, "teamMembers": -1},
    "enterprise": {"leadSources": -1, "teamMembers": -1},  # -1 = unlimited
}

BASE_PLAN_PRICES = {
    "starter": 29.99,
    "growth": 69.99,
    "pro": 119.99,
    "enterprise": 0,  # Custom pricing
}

BASE_PLAN_NAMES = {
    "starter": "Starter",
    "growth": "Growth",
    "pro": "Pro",
    "enterprise": "Enterprise",
}

# ENHANCEMENT SUBSCRIPTIONS
# Target: 55-60% margin
# Cost basis: Enhancement $0.18/ea, Criminal $2.00/ea, DNC $0.025/ea
ENHANCEMENT_PLAN_CREDITS = {
    "enhance-starter": {"enhancement": 50, "criminal": 1, "dnc": 50},    # Cost: $12.25 → 58% margin
    "enhance-growth": {"enhancement": 100, "criminal": 2, "dnc": 100},  # Cost: $24.50 → 58% margin
    "enhance-pro": {"enhancement": 175, "criminal": 3, "dnc": 150},     # Cost: $41.25 → 58% margin
}

ENHANCEMENT_PLAN_PRICES = {
    "enhance-starter": 29,
    "enhance-growth": 59,
    "enhance-pro": 99,
}

ENHANCEMENT_PLAN_NAMES = {
    "enhance-starter": "Enhancement Starter",
    "enhance-growth": "Enhancement Growth",
    "enhance-pro": "Enhancement Pro",
}

# CREDIT ADD-ON PACKAGES (One-time, never expire)
# Target: 75% margin
CREDIT_PACKAGES = {
    "enhancement-50": {"type": "enhancement", "amount": 50, "price": 35},
    "enhancement-100": {"type": "enhancement", "amount": 100, "price": 70},
    "enhancement-250": {"type": "enhancement", "amount": 250, "price": 175},
    "criminal-5": {"type": "criminal", "amount": 5, "price": 40},
    "criminal-10": {"type": "criminal", "amount": 10, "price": 75},
    "dnc-200": {"type": "dnc", "amount": 200, "price": 20},
    "dnc-500": {"type": "dnc", "amount": 500, "price": 50},
}

# ===========================================
# LEGACY PLAN CONFIGURATION (Backward compatibility)
# ===========================================
PLAN_CREDITS = {
    "solo": {"enhancement": 50, "criminal": 2, "dnc": 100},
    "team": {"enhancement": 100, "criminal": 3, "dnc": 200},
    "brokerage": {"enhancement": 200, "criminal": 5, "dnc": 300},
    "enterprise": {"enhancement": 500, "criminal": 10, "dnc": 500},
}

PLAN_LIMITS = {
    "solo": {"leadSources": 3, "teamMembers": -1},      # Unlimited team members
    "team": {"leadSources": 5, "teamMembers": -1},
    "brokerage": {"leadSources": 7, "teamMembers": -1},
    "enterprise": {"leadSources": 10, "teamMembers": -1},
}

PLAN_PRICES = {
    "solo": 49.99,
    "team": 89.99,
    "brokerage": 164.99,
    "enterprise": 349.99,
}

PLAN_NAMES = {
    "solo": "Solo Agent",
    "team": "Team",
    "brokerage": "Brokerage",
    "enterprise": "Enterprise",
}


# User-friendly billing endpoints (accepts X-User-ID instead of X-Organization-ID)
@supabase_api.route("/user/subscription", methods=["GET"])
def get_user_subscription():
    """Get subscription for the current user's organization, including credits"""
    try:
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        org_id = get_org_id_for_user(user_id)

        # Get user's credit information
        user_credits = credit_service.get_user_credits(user_id)

        # Default credits if no user credits found
        default_credits = {
            "enhancement": {"used": 0, "limit": 25, "purchased": 0},
            "criminal": {"used": 0, "limit": 1, "purchased": 0},
            "dnc": {"used": 0, "limit": 50, "purchased": 0},
        }

        if not org_id:
            # Return default solo subscription if no organization
            return jsonify({
                "success": True,
                "data": {
                    "plan": "solo",
                    "status": "active",
                    "trialEndsAt": None,
                    "currentPeriodEnd": datetime.now().isoformat(),
                    "cancelAtPeriodEnd": False,
                    "credits": default_credits,
                    "usage": {
                        "teamMembers": {"current": 1, "limit": 1},
                        "leadSources": {"current": 0, "limit": 3},
                    }
                }
            }), 200

        subscription = subscription_service.get_subscription(org_id)

        # Determine plan and its limits
        plan_id = subscription.get("plan", "solo")
        if plan_id not in PLAN_CREDITS:
            plan_id = "solo"

        plan_credits = PLAN_CREDITS.get(plan_id, PLAN_CREDITS["solo"])
        plan_limits = PLAN_LIMITS.get(plan_id, PLAN_LIMITS["solo"])

        # Calculate credits - use user_credits if available, otherwise plan defaults
        if user_credits:
            # Total available = plan credits + purchased (bundle) credits
            enhancement_limit = plan_credits["enhancement"]
            criminal_limit = plan_credits["criminal"]
            dnc_limit = plan_credits["dnc"]

            # Purchased credits from bundles
            enhancement_purchased = user_credits.get("bundle_enhancement_credits", 0)
            criminal_purchased = user_credits.get("bundle_criminal_credits", 0)
            dnc_purchased = user_credits.get("bundle_dnc_credits", 0)

            # Calculate used credits (plan allocation - current remaining)
            enhancement_remaining = user_credits.get("plan_enhancement_credits", 0)
            criminal_remaining = user_credits.get("plan_criminal_credits", 0)
            dnc_remaining = user_credits.get("plan_dnc_credits", 0)

            # Used = original allocation - remaining
            enhancement_used = max(0, enhancement_limit - enhancement_remaining)
            criminal_used = max(0, criminal_limit - criminal_remaining)
            dnc_used = max(0, dnc_limit - dnc_remaining)

            credits = {
                "enhancement": {
                    "used": enhancement_used,
                    "limit": enhancement_limit,
                    "purchased": enhancement_purchased,
                },
                "criminal": {
                    "used": criminal_used,
                    "limit": criminal_limit,
                    "purchased": criminal_purchased,
                },
                "dnc": {
                    "used": dnc_used,
                    "limit": dnc_limit,
                    "purchased": dnc_purchased,
                },
            }
        else:
            credits = {
                "enhancement": {"used": 0, "limit": plan_credits["enhancement"], "purchased": 0},
                "criminal": {"used": 0, "limit": plan_credits["criminal"], "purchased": 0},
                "dnc": {"used": 0, "limit": plan_credits["dnc"], "purchased": 0},
            }

        # Add credits and updated usage to subscription data
        subscription["credits"] = credits
        subscription["usage"] = {
            "teamMembers": subscription.get("usage", {}).get("teamMembers", {"current": 1, "limit": plan_limits["teamMembers"]}),
            "leadSources": subscription.get("usage", {}).get("leadSources", {"current": 0, "limit": plan_limits["leadSources"]}),
        }

        return jsonify({"success": True, "data": subscription}), 200
    except Exception as e:
        logger.error(f"Error getting user subscription: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/user/payment-methods", methods=["GET"])
def get_user_payment_methods():
    """Get payment methods for the current user's organization"""
    try:
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        org_id = get_org_id_for_user(user_id)
        if not org_id:
            return jsonify({"success": True, "data": []}), 200

        payment_methods = subscription_service.get_payment_methods(org_id)
        return jsonify({"success": True, "data": payment_methods}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/user/billing-history", methods=["GET"])
def get_user_billing_history():
    """Get billing history for the current user's organization"""
    try:
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        org_id = get_org_id_for_user(user_id)
        if not org_id:
            return jsonify({"success": True, "data": []}), 200

        billing_history = subscription_service.get_billing_history(org_id)
        return jsonify({"success": True, "data": billing_history}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/user/subscription/cancel", methods=["POST"])
def cancel_user_subscription():
    """Cancel subscription for the current user's organization"""
    try:
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        org_id = get_org_id_for_user(user_id)
        if not org_id:
            return jsonify({"success": False, "error": "No organization found"}), 404

        success = subscription_service.cancel_subscription(org_id)
        if not success:
            return jsonify({"success": False, "error": "Failed to cancel subscription"}), 500

        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/user/subscription/reactivate", methods=["POST"])
def reactivate_user_subscription():
    """Reactivate subscription for the current user's organization"""
    try:
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        org_id = get_org_id_for_user(user_id)
        if not org_id:
            return jsonify({"success": False, "error": "No organization found"}), 404

        success = subscription_service.reactivate_subscription(org_id)
        if not success:
            return jsonify({"success": False, "error": "Failed to reactivate subscription"}), 500

        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/user/payment-methods/<payment_method_id>/default", methods=["POST"])
def set_user_default_payment_method(payment_method_id):
    """Set default payment method for the current user's organization"""
    try:
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        org_id = get_org_id_for_user(user_id)
        if not org_id:
            return jsonify({"success": False, "error": "No organization found"}), 404

        success = subscription_service.set_default_payment_method(org_id, payment_method_id)
        if not success:
            return jsonify({"success": False, "error": "Failed to set default payment method"}), 500

        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/user/payment-methods/<payment_method_id>", methods=["DELETE"])
def delete_user_payment_method(payment_method_id):
    """Delete payment method for the current user's organization"""
    try:
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        org_id = get_org_id_for_user(user_id)
        if not org_id:
            return jsonify({"success": False, "error": "No organization found"}), 404

        success = subscription_service.delete_payment_method(org_id, payment_method_id)
        if not success:
            return jsonify({"success": False, "error": "Failed to delete payment method"}), 500

        return jsonify({"success": True}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Credit package configuration (should match frontend lib/plans.ts)
CREDIT_PACKAGES = {
    "enhancement-50": {"type": "enhancement", "amount": 50, "price": 15},
    "enhancement-100": {"type": "enhancement", "amount": 100, "price": 25},
    "enhancement-250": {"type": "enhancement", "amount": 250, "price": 50},
    "criminal-5": {"type": "criminal", "amount": 5, "price": 20},
    "criminal-10": {"type": "criminal", "amount": 10, "price": 35},
    "dnc-200": {"type": "dnc", "amount": 200, "price": 10},
    "dnc-500": {"type": "dnc", "amount": 500, "price": 20},
}


@supabase_api.route("/user/credits/purchase", methods=["POST"])
def purchase_credits():
    """Purchase additional credits for the user"""
    try:
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        data = request.get_json()
        package_id = data.get("packageId")

        if not package_id:
            return jsonify({"success": False, "error": "Package ID is required"}), 400

        if package_id not in CREDIT_PACKAGES:
            return jsonify({"success": False, "error": "Invalid package ID"}), 400

        package = CREDIT_PACKAGES[package_id]
        credit_type = package["type"]
        amount = package["amount"]

        # Add credits to user's bundle credits
        success, message = credit_service.add_credits(
            user_id=user_id,
            credit_type=credit_type,
            amount=amount,
            source="bundle",
            description=f"Purchased {amount} {credit_type} credits (package: {package_id})"
        )

        if success:
            return jsonify({
                "success": True,
                "message": f"Successfully added {amount} {credit_type} credits",
                "package": package_id
            }), 200
        else:
            return jsonify({"success": False, "error": message}), 500

    except Exception as e:
        logger.error(f"Error purchasing credits: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/user/subscription/change-plan", methods=["POST"])
def change_user_plan():
    """Change the user's subscription plan"""
    try:
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        data = request.get_json()
        new_plan = data.get("newPlan")

        if not new_plan:
            return jsonify({"success": False, "error": "New plan is required"}), 400

        if new_plan not in PLAN_CREDITS:
            return jsonify({"success": False, "error": "Invalid plan ID"}), 400

        org_id = get_org_id_for_user(user_id)
        if not org_id:
            return jsonify({"success": False, "error": "No organization found"}), 404

        # Update user's plan credits based on new plan
        new_credits = PLAN_CREDITS[new_plan]
        success, message = credit_service.set_plan_credits(
            user_id=user_id,
            enhancement=new_credits["enhancement"],
            criminal=new_credits["criminal"],
            dnc=new_credits["dnc"]
        )

        if not success:
            return jsonify({"success": False, "error": f"Failed to update credits: {message}"}), 500

        # TODO: In a production environment, this would also:
        # 1. Update the Stripe subscription
        # 2. Handle proration
        # 3. Update the subscription record in the database

        return jsonify({
            "success": True,
            "message": f"Plan changed to {PLAN_NAMES.get(new_plan, new_plan)}",
            "newPlan": new_plan
        }), 200

    except Exception as e:
        logger.error(f"Error changing plan: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/lead-sources/<source_id>/sync-now", methods=["POST"])
def trigger_immediate_sync(source_id):
    """Trigger an immediate sync for all leads associated with a lead source (runs in background)"""
    try:
        import uuid
        import threading
        from app.service.sync_status_tracker import get_tracker

        # Get user ID from headers
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({"success": False, "error": "User ID not provided"}), 400

        # Check if force_sync is requested (bypasses minimum interval)
        request_data = request.get_json() if request.is_json else {}
        force_sync = request_data.get('force_sync', False)

        # Get the lead source
        source = lead_source_service.get_by_id(source_id)
        if not source:
            return (
                jsonify({"success": False, "error": "Lead source not found"}),
                404,
            )

        # Check if source is active
        if isinstance(source, dict):
            is_active = source.get("is_active", False)
            source_name = source.get("source_name")
        else:
            is_active = source.is_active
            source_name = source.source_name

        if not is_active:
            return (
                jsonify({"success": False, "error": "Lead source is not active"}),
                400,
            )

        # Get all leads for this source and user (no limit - get all leads)
        leads = lead_service.get_by_source_and_user(source_name, user_id, limit=10000, offset=0)

        logger.info(f"Sync trigger: source_name='{source_name}', user_id='{user_id}', leads_found={len(leads) if leads else 0}")

        if not leads:
            # Try without user filter to see if leads exist for other users
            all_source_leads = lead_service.get_by_source(source_name, limit=10, offset=0)
            if all_source_leads:
                logger.warning(f"Found {len(all_source_leads)} leads for source '{source_name}' but none for user '{user_id}'")
                return (
                    jsonify({"success": False, "error": f"No leads found for source '{source_name}' belonging to your account. Found {len(all_source_leads)} leads for other users."}),
                    404,
                )
            return (
                jsonify({"success": False, "error": f"No leads found for source '{source_name}'"}),
                404,
            )

        # Generate unique sync ID for tracking
        sync_id = str(uuid.uuid4())
        
        # Initialize sync status
        tracker = get_tracker()
        tracker.start_sync(sync_id, source_id, source_name, len(leads), user_id)
        
        # Run sync in background thread
        def run_sync():
            try:
                logger.info(f"Starting background sync for {source_name} - {len(leads)} leads (force_sync={force_sync})")
                # Use generic sync method that handles all platforms
                lead_source_service.sync_all_sources_bulk_with_tracker(
                    sync_id, source_name, leads, user_id, tracker, force_sync=force_sync
                )
            except Exception as e:
                logger.error(f"Error in background sync: {str(e)}", exc_info=True)
                tracker.complete_sync(sync_id, error=str(e))
        
        thread = threading.Thread(target=run_sync, daemon=True)
        thread.start()
        
        # Return immediately with sync ID for tracking
        return jsonify({
            "success": True,
            "sync_id": sync_id,
            "message": "Sync started in background",
            "status_url": f"/api/supabase/sync-status/{sync_id}"
        }), 202  # 202 Accepted - processing started

    except Exception as e:
        logger.error(f"Error triggering immediate sync: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/lead-sources/<source_id>/needs-action-sweep", methods=["POST"])
def trigger_needs_action_sweep(source_id):
    """Trigger a Needs Action sweep for ReferralExchange (or similar urgent sweep for other platforms)"""
    try:
        import uuid
        import threading
        from app.service.sync_status_tracker import get_tracker

        # Get user ID from headers
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({"success": False, "error": "User ID not provided"}), 400

        # Get the lead source
        source = lead_source_service.get_by_id(source_id)
        if not source:
            return jsonify({"success": False, "error": "Lead source not found"}), 404

        # Get source name
        if isinstance(source, dict):
            source_name = source.get("source_name")
        else:
            source_name = source.source_name

        # Currently only ReferralExchange is supported
        # Normalize source name for comparison (case-insensitive, no spaces)
        normalized_name = (source_name or "").lower().replace(" ", "")
        if normalized_name != "referralexchange":
            return jsonify({
                "success": False,
                "error": f"Needs Action sweep not yet implemented for {source_name}"
            }), 400

        # Generate unique sync ID for tracking
        sync_id = str(uuid.uuid4())

        # Initialize sync status
        tracker = get_tracker()
        tracker.start_sync(sync_id, source_id, f"{source_name} Needs Action", 0, user_id)

        # Run sweep in background thread
        def run_sweep():
            try:
                logger.info(f"Starting Needs Action sweep for {source_name}")
                from app.referral_scrapers.referral_exchange.referral_exchange_service import ReferralExchangeService

                # Get credentials from lead source settings
                source_settings = lead_source_service.get_by_id(source_id)
                email = None
                password = None
                if source_settings:
                    if isinstance(source_settings, dict):
                        metadata = source_settings.get('metadata', {}) or {}
                    else:
                        metadata = getattr(source_settings, 'metadata', {}) or {}
                    creds = metadata.get('credentials', {}) if isinstance(metadata, dict) else {}
                    email = creds.get('email')
                    password = creds.get('password')

                if not email or not password:
                    logger.error("No credentials found for ReferralExchange")
                    tracker.complete_sync(sync_id, error="No credentials configured for ReferralExchange")
                    return

                # Create service and manually set credentials
                service = ReferralExchangeService()
                service.email = email
                service.password = password

                results = service.run_standalone_need_action_sweep()

                # Update tracker with results
                tracker.update_progress(
                    sync_id,
                    processed=results.get('updated', 0),
                    total_leads=results.get('total_checked', 0),
                    successful=results.get('updated', 0),
                    failed=results.get('errors', 0),
                    skipped=0,
                    current_lead=None
                )

                if results.get('errors', 0) > 0:
                    tracker.complete_sync(sync_id, error=f"{results['errors']} leads failed")
                else:
                    tracker.complete_sync(sync_id)

                logger.info(f"Needs Action sweep completed: {results}")

            except Exception as e:
                logger.error(f"Error in Needs Action sweep: {str(e)}", exc_info=True)
                tracker.complete_sync(sync_id, error=str(e))

        thread = threading.Thread(target=run_sweep, daemon=True)
        thread.start()

        return jsonify({
            "success": True,
            "sync_id": sync_id,
            "message": "Needs Action sweep started in background",
            "status_url": f"/api/supabase/sync-status/{sync_id}"
        }), 202

    except Exception as e:
        logger.error(f"Error triggering Needs Action sweep: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/import-fub-leads", methods=["POST"])
def import_fub_leads(user_id=None):
    """Import all leads from Follow Up Boss API for a specific user"""
    try:
        import time
        from pathlib import Path

        start_time = time.time()
        timings = {}

        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file_path = log_dir / "import_fub_leads.log"

        def log_progress(message: str) -> None:
            timestamp = datetime.utcnow().isoformat()
            formatted = f"[{timestamp}] {message}"
            logger.info(message)
            print(formatted, flush=True)
            try:
                with log_file_path.open("a", encoding="utf-8") as log_file:
                    log_file.write(formatted + "\n")
            except Exception as log_error:
                logger.debug(f"Unable to write import log entry: {log_error}")

        log_progress("=" * 80)
        log_progress("Starting FUB lead import")

        # Get user_id from request or parameter
        if not user_id:
            user_id = request.headers.get('X-User-ID') or request.get_json().get('user_id')
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400

        log_progress(f"Importing for user: {user_id}")

        # Get user's FUB API key
        from app.service.fub_api_key_service import FUBAPIKeyServiceSingleton
        fub_key_service = FUBAPIKeyServiceSingleton.get_instance()
        user_api_key = fub_key_service.get_api_key_for_user(user_id)

        if not user_api_key:
            return jsonify({"success": False, "error": "No FUB API key found for user"}), 400

        log_progress("Retrieved user's FUB API key")

        from app.database.fub_api_client import FUBApiClient
        from app.models.lead import Lead

        log_progress("Initializing FUB API client with user's key")
        fub_client = FUBApiClient(user_api_key)
        timings["client_init_seconds"] = round(time.time() - start_time, 2)
        log_progress(f"FUB API client ready in {timings['client_init_seconds']}s")

        log_progress("Fetching active lead sources for user")
        active_sources = lead_source_service.get_active_sources(user_id)
        source_names = set()
        for source_data in active_sources:
            if isinstance(source_data, dict):
                source_names.add(source_data.get("source_name"))
            else:
                source_names.add(source_data.source_name)

        log_progress(f"Active sources for user: {', '.join(sorted(source_names))}")
        log_progress(f"Note: New sources from FUB will be auto-discovered and created as inactive")

        fetch_start = time.time()
        all_people = []
        limit = 100
        next_cursor = None
        total_in_fub = None
        request_count = 0

        log_progress(f"Fetching people from FUB (page size {limit})")

        while True:
            request_count += 1
            try:
                response = fub_client.get_people(limit=limit, page=1 if request_count == 1 else None, next_cursor=next_cursor)
                people = response.get("people", [])
                metadata = response.get("_metadata", {})

                if total_in_fub is None and "total" in metadata:
                    total_in_fub = metadata["total"]
                    log_progress(f"FUB reports {total_in_fub} total people")

                if not people:
                    log_progress(f"No people found on request {request_count}")
                    break

                all_people.extend(people)
                log_progress(f"Request {request_count}: fetched {len(people)} (running total {len(all_people)})")

                if total_in_fub and len(all_people) >= total_in_fub:
                    log_progress("All people fetched based on metadata total")
                    break

                # Check if there's a next cursor for pagination
                next_cursor = metadata.get("next")
                if not next_cursor:
                    log_progress("No more pages available")
                    break

                if len(people) < limit:
                    log_progress(f"Last page reached (fewer than {limit} records)")
                    break

            except Exception as fetch_error:
                logger.error(f"Error fetching request {request_count}: {fetch_error}")
                log_progress(f"Error fetching request {request_count}: {fetch_error}")
                raise

        fetch_time = time.time() - fetch_start
        timings["fub_fetch_seconds"] = round(fetch_time, 2)
        log_progress(f"Fetched {len(all_people)} people from FUB in {timings['fub_fetch_seconds']}s")

        # Auto-discover new lead sources
        log_progress("Auto-discovering new lead sources")
        discovered_sources = set()
        for person in all_people:
            source = person.get("source")
            if source and source not in source_names:
                discovered_sources.add(source)

        # Create new lead sources for discovered ones
        new_sources_created = 0
        for source_name in discovered_sources:
            try:
                lead_source_service.create_or_get_source(user_id, source_name, auto_discovered=True)
                new_sources_created += 1
                log_progress(f"Auto-created inactive lead source: {source_name}")
            except Exception as create_error:
                logger.error(f"Failed to create lead source {source_name}: {create_error}")
                log_progress(f"Failed to create lead source {source_name}: {create_error}")

        if new_sources_created > 0:
            log_progress(f"Auto-created {new_sources_created} new lead sources")

        # Load alias mappings for source name resolution
        from app.service.lead_source_mapping_service import LeadSourceMappingSingleton
        mapping_service = LeadSourceMappingSingleton.get_instance()
        log_progress("Loading source alias mappings")

        # Build a lookup dict for alias resolution
        alias_mappings = {}
        try:
            all_aliases = mapping_service.get_all_aliases(user_id)
            for alias in all_aliases:
                alias_mappings[alias.get("alias_name")] = alias.get("canonical_source_name")
            if alias_mappings:
                log_progress(f"Loaded {len(alias_mappings)} alias mappings")
        except Exception as alias_error:
            logger.error(f"Error loading alias mappings: {alias_error}")
            log_progress(f"Warning: Could not load alias mappings: {alias_error}")

        # Update source_names to include auto-discovered sources (they're inactive, so won't be imported yet)
        all_user_sources = lead_source_service.get_all(user_id=user_id)
        updated_source_names = set()
        for source_data in all_user_sources:
            if isinstance(source_data, dict):
                updated_source_names.add(source_data.get("source_name"))
            else:
                updated_source_names.add(source_data.source_name)

        filter_start = time.time()
        filtered_leads = [
            person for person in all_people
            if person.get("source") in updated_source_names and person.get("id")
        ]
        filter_time = time.time() - filter_start
        timings["filter_seconds"] = round(filter_time, 2)
        timings["filtered_count"] = len(filtered_leads)
        timings["fub_total_people"] = len(all_people)
        timings["new_sources_created"] = new_sources_created
        log_progress(f"Filtered to {len(filtered_leads)} leads with valid IDs in {timings['filter_seconds']}s")

        results = {
            "total_fetched": len(all_people),
            "total_filtered": len(filtered_leads),
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "details": [],
        }

        db_check_start = time.time()
        log_progress("Checking Supabase for existing leads")
        fub_ids_to_check = [str(person.get("id")) for person in filtered_leads]

        existing_leads_map = {}
        try:
            from app.database.supabase_client import SupabaseClientSingleton

            supabase = SupabaseClientSingleton.get_instance()
            existing_leads_result = (
                supabase.table("leads")
                .select("id,fub_person_id")
                .in_("fub_person_id", fub_ids_to_check)
                .eq("user_id", user_id)  # Only check leads belonging to this user
                .execute()
            )
            existing_leads_map = {
                lead["fub_person_id"]: lead["id"]
                for lead in existing_leads_result.data
                if lead.get("fub_person_id") and lead.get("id")
            }
            existing_fub_ids = set(existing_leads_map.keys())
        except Exception as db_error:
            logger.error(f"Error fetching existing leads: {db_error}")
            log_progress(f"Error checking existing leads: {db_error}")
            existing_fub_ids = set()
            existing_leads_map = {}

        timings["existing_lookup_seconds"] = round(time.time() - db_check_start, 2)
        timings["existing_count"] = len(existing_fub_ids)
        log_progress(
            f"Existing lead lookup completed in {timings['existing_lookup_seconds']}s "
            f"({timings['existing_count']} existing leads)"
        )

        prep_start = time.time()
        leads_to_insert = []
        leads_to_update = []
        processed_fub_ids = set()
        processed_count = 0
        skipped_duplicates = 0

        log_progress(f"Processing {len(filtered_leads)} filtered leads")
        for person_data in filtered_leads:
            fub_person_id = str(person_data.get("id"))
            if fub_person_id in processed_fub_ids:
                skipped_duplicates += 1
                continue
            processed_fub_ids.add(fub_person_id)
            processed_count += 1
            lead_obj = Lead.from_fub(person_data)
            lead_dict = {
                key: value
                for key, value in lead_obj.to_dict().items()
                if value is not None
            }
            lead_dict.pop("fub_id", None)
            lead_dict["fub_person_id"] = fub_person_id
            lead_dict["user_id"] = user_id  # Set user ownership
            if lead_dict.get("price") is None:
                lead_dict["price"] = 0
            if isinstance(lead_dict.get("tags"), list):
                lead_dict["tags"] = json.dumps(lead_dict["tags"])

            # Resolve source alias to canonical source name
            original_source = lead_dict.get("source")
            if original_source and original_source in alias_mappings:
                canonical_source = alias_mappings[original_source]
                if canonical_source:
                    lead_dict["source"] = canonical_source

            if fub_person_id in existing_fub_ids:
                lead_dict["id"] = existing_leads_map[fub_person_id]
                leads_to_update.append(lead_dict)
            else:
                if not lead_dict.get("id"):
                    lead_dict["id"] = str(uuid.uuid4())
                leads_to_insert.append(lead_dict)

        prep_time = time.time() - prep_start
        timings["prepare_seconds"] = round(prep_time, 2)
        timings["to_insert"] = len(leads_to_insert)
        timings["to_update"] = len(leads_to_update)
        timings["processed_count"] = processed_count
        timings["skipped_duplicates"] = skipped_duplicates
        log_progress(
            f"Prepared {processed_count} leads ({skipped_duplicates} duplicates skipped), "
            f"{len(leads_to_insert)} inserts, {len(leads_to_update)} updates in {timings['prepare_seconds']}s"
        )
        if leads_to_insert:
            log_progress(
                f"Insert payload columns: {sorted(leads_to_insert[0].keys())}"
            )
        if leads_to_update:
            log_progress(
                f"Update payload columns: {sorted(leads_to_update[0].keys())}"
            )
        log_progress(
            f"Prepared {len(leads_to_insert)} inserts and {len(leads_to_update)} updates "
            f"in {timings['prepare_seconds']}s"
        )

        insert_time = 0.0
        if leads_to_insert:
            try:
                insert_start = time.time()
                log_progress(f"Batch inserting {len(leads_to_insert)} leads")
                insert_result = supabase.table("leads").insert(leads_to_insert).execute()
                results["inserted"] = len(insert_result.data) if insert_result.data else len(leads_to_insert)
                insert_time = time.time() - insert_start
                log_progress(
                    f"Inserted {results['inserted']} leads in {round(insert_time, 2)}s"
                )
            except Exception as insert_error:
                log_progress(f"Batch insert error: {insert_error}")
                logger.error(f"Batch insert error: {insert_error}")
                results["errors"] += len(leads_to_insert)

        update_time = 0.0
        if leads_to_update:
            try:
                update_start = time.time()
                log_progress(f"Batch updating {len(leads_to_update)} leads")
                update_result = supabase.table("leads").upsert(
                    leads_to_update, on_conflict="id"
                ).execute()
                results["updated"] = len(update_result.data) if update_result.data else len(leads_to_update)
                update_time = time.time() - update_start
                log_progress(
                    f"Updated {results['updated']} leads in {round(update_time, 2)}s"
                )
            except Exception as update_error:
                log_progress(f"Batch update error: {update_error}")
                logger.error(f"Batch update error: {update_error}")
                results["errors"] += len(leads_to_update)

        total_time = time.time() - start_time
        timings["insert_seconds"] = round(insert_time, 2)
        timings["update_seconds"] = round(update_time, 2)
        timings["total_seconds"] = round(total_time, 2)

        log_progress(
            f"Import complete: {results['inserted']} inserted, "
            f"{results['updated']} updated, {results['errors']} errors"
        )
        log_progress(f"Total import time {timings['total_seconds']}s")
        log_progress("=" * 80)

        results["timings"] = timings
        return jsonify({"success": True, "data": results}), 200

    except Exception as error:
        logger.error(f"Error importing FUB leads: {error}")
        return jsonify({"success": False, "error": str(error)}), 500


def register_supabase_api(app):
    app.register_blueprint(supabase_api)


# Lead AI Settings
@supabase_api.route("/lead-ai-settings/<person_id>", methods=["GET"])
def get_lead_ai_settings(person_id):
    """Get AI settings for a specific lead."""
    try:
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400
        
        # Get organization
        user_result = supabase.table("users").select("organization_id").eq("id", user_id).execute()
        if not user_result.data:
            return jsonify({"success": False, "error": "User not found"}), 404
        
        organization_id = user_result.data[0].get("organization_id")
        
        # Get AI settings
        from app.ai_agent.lead_ai_settings_service import LeadAISettingsServiceSingleton
        import asyncio
        
        lead_ai_service = LeadAISettingsServiceSingleton.get_instance(supabase)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        ai_enabled = loop.run_until_complete(
            lead_ai_service.is_ai_enabled_for_lead(person_id, organization_id, user_id)
        )
        
        return jsonify({
            "success": True,
            "data": {
                "person_id": person_id,
                "ai_enabled": ai_enabled if ai_enabled is not None else "unset",
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting lead AI settings: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/lead-ai-settings/<person_id>/toggle", methods=["POST"])
def toggle_lead_ai(person_id):
    """
    Toggle AI for a specific lead.
    Also adds/removes 'AI Follow-up' tag in FUB.
    """
    try:
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400
        
        data = request.json
        enable = data.get("enable", True)
        
        # Get organization
        user_result = supabase.table("users").select("organization_id").eq("id", user_id).execute()
        if not user_result.data:
            return jsonify({"success": False, "error": "User not found"}), 404
        
        organization_id = user_result.data[0].get("organization_id")
        
        # Get AI settings service
        from app.ai_agent.lead_ai_settings_service import LeadAISettingsServiceSingleton
        import asyncio
        
        lead_ai_service = LeadAISettingsServiceSingleton.get_instance(supabase)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Toggle AI setting
        if enable:
            success = loop.run_until_complete(
                lead_ai_service.enable_ai_for_lead(
                    fub_person_id=person_id,
                    organization_id=organization_id,
                    user_id=user_id,
                    reason='manual_toggle',
                    enabled_by=user_id,
                )
            )
        else:
            success = loop.run_until_complete(
                lead_ai_service.disable_ai_for_lead(
                    fub_person_id=person_id,
                    organization_id=organization_id,
                )
            )
        
        if not success:
            return jsonify({"success": False, "error": "Failed to update AI settings"}), 500

        # Sync with FUB tag
        try:
            from app.database.fub_api_client import FUBApiClient
            fub_client = FUBApiClient(api_key=CREDS.FUB_API_KEY)

            if enable:
                # Add "AI Follow-up" tag
                fub_client.add_tag(person_id, "AI Follow-up")
                logger.info(f"Added 'AI Follow-up' tag to person {person_id}")
            else:
                # Remove "AI Follow-up" tag
                fub_client.remove_tag(person_id, "AI Follow-up")
                logger.info(f"Removed 'AI Follow-up' tag from person {person_id}")
        except Exception as tag_error:
            logger.warning(f"Failed to sync FUB tag: {tag_error}")
            # Don't fail the request if tag sync fails

        # Trigger proactive outreach when enabling
        if enable:
            try:
                from app.ai_agent.proactive_outreach_orchestrator import trigger_proactive_outreach
                loop.run_until_complete(
                    trigger_proactive_outreach(
                        fub_person_id=int(person_id),
                        organization_id=organization_id,
                        user_id=user_id,
                        trigger_reason="frontend_toggle",
                        enable_type="manual",
                        supabase_client=supabase,
                    )
                )
            except Exception as outreach_error:
                logger.error(f"Proactive outreach failed for {person_id}: {outreach_error}")
                # Don't fail the toggle if outreach fails

        return jsonify({
            "success": True,
            "data": {
                "person_id": person_id,
                "ai_enabled": enable,
                "tag_synced": True,
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error toggling lead AI: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@supabase_api.route("/lead-ai-settings/bulk-toggle", methods=["POST"])
def bulk_toggle_lead_ai():
    """
    Bulk toggle AI for multiple leads.
    Also adds/removes 'AI Follow-up' tags in FUB.
    """
    try:
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return jsonify({"success": False, "error": "User ID is required"}), 400
        
        data = request.json
        person_ids = data.get("person_ids", [])
        enable = data.get("enable", True)
        reason = data.get("reason", "bulk_toggle")
        
        if not person_ids:
            return jsonify({"success": False, "error": "person_ids required"}), 400
        
        # Get organization
        user_result = supabase.table("users").select("organization_id").eq("id", user_id).execute()
        if not user_result.data:
            return jsonify({"success": False, "error": "User not found"}), 404
        
        organization_id = user_result.data[0].get("organization_id")
        
        # Get AI settings service
        from app.ai_agent.lead_ai_settings_service import LeadAISettingsServiceSingleton
        from app.database.fub_api_client import FUBApiClient
        import asyncio
        
        lead_ai_service = LeadAISettingsServiceSingleton.get_instance(supabase)
        fub_client = FUBApiClient(api_key=CREDS.FUB_API_KEY)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Bulk enable/disable
        if enable:
            result = loop.run_until_complete(
                lead_ai_service.bulk_enable_ai(
                    fub_person_ids=person_ids,
                    organization_id=organization_id,
                    user_id=user_id,
                    reason=reason,
                    enabled_by=user_id,
                )
            )
            # Add tags
            for person_id in person_ids:
                try:
                    fub_client.add_tag(person_id, "AI Follow-up")
                except Exception as e:
                    logger.warning(f"Failed to add tag for {person_id}: {e}")
        else:
            # Disable individually
            success_count = 0
            failed_count = 0
            for person_id in person_ids:
                try:
                    success = loop.run_until_complete(
                        lead_ai_service.disable_ai_for_lead(person_id, organization_id)
                    )
                    if success:
                        success_count += 1
                        fub_client.remove_tag(person_id, "AI Follow-up")
                    else:
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Error disabling AI for {person_id}: {e}")
                    failed_count += 1
            
            result = {
                "success_count": success_count,
                "failed_count": failed_count,
                "total": len(person_ids),
            }
        
        return jsonify({"success": True, "data": result}), 200
    
    except Exception as e:
        logger.error(f"Error bulk toggling lead AI: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
