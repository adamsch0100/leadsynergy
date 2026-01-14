"""
Lead Source Mappings API Routes - Alias management and source merging.
"""

from flask import request, jsonify
import logging

from app.lead_source_mappings import lead_source_mappings_bp
from app.service.lead_source_mapping_service import LeadSourceMappingSingleton

logger = logging.getLogger(__name__)


def get_user_id_from_request():
    """Extract user ID from request headers or body."""
    user_id = request.headers.get("X-User-ID")
    if not user_id and request.is_json:
        data = request.get_json(silent=True)
        if data:
            user_id = data.get("user_id")
    return user_id


# =============================================================================
# Alias Mapping Endpoints
# =============================================================================


@lead_source_mappings_bp.route("/mappings", methods=["GET"])
def get_all_mappings():
    """
    Get all alias mappings for the current user.
    Returns aliases with their canonical source names.
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        mapping_service = LeadSourceMappingSingleton.get_instance()
        aliases = mapping_service.get_all_aliases(user_id)

        return jsonify({"success": True, "data": aliases})

    except Exception as e:
        logger.error(f"Error getting mappings: {e}")
        return jsonify({"error": str(e)}), 500


@lead_source_mappings_bp.route("/mappings", methods=["POST"])
def create_mapping():
    """
    Create a new alias mapping.

    Body:
        - alias_name: The variant source name to map
        - canonical_source_id: The ID of the canonical source to map to
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    alias_name = data.get("alias_name")
    canonical_source_id = data.get("canonical_source_id")

    if not alias_name:
        return jsonify({"error": "alias_name is required"}), 400

    if not canonical_source_id:
        return jsonify({"error": "canonical_source_id is required"}), 400

    try:
        mapping_service = LeadSourceMappingSingleton.get_instance()
        alias = mapping_service.create_alias(alias_name, canonical_source_id, user_id)

        if alias:
            return jsonify({"success": True, "data": alias.to_dict()}), 201
        else:
            return jsonify({"error": "Failed to create alias"}), 500

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating mapping: {e}")
        return jsonify({"error": str(e)}), 500


@lead_source_mappings_bp.route("/mappings/<alias_id>", methods=["DELETE"])
def delete_mapping(alias_id):
    """
    Delete an alias mapping.
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        mapping_service = LeadSourceMappingSingleton.get_instance()
        success = mapping_service.delete_alias(alias_id, user_id)

        if success:
            return jsonify({"success": True, "message": "Alias deleted"})
        else:
            return jsonify({"error": "Failed to delete alias"}), 500

    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error(f"Error deleting mapping: {e}")
        return jsonify({"error": str(e)}), 500


@lead_source_mappings_bp.route("/<source_id>/aliases", methods=["GET"])
def get_source_aliases(source_id):
    """
    Get all aliases that point to a specific canonical source.
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        mapping_service = LeadSourceMappingSingleton.get_instance()
        aliases = mapping_service.get_aliases_for_source(source_id, user_id)

        return jsonify(
            {"success": True, "data": [alias.to_dict() for alias in aliases]}
        )

    except Exception as e:
        logger.error(f"Error getting source aliases: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Source Merge Endpoint
# =============================================================================


@lead_source_mappings_bp.route("/merge", methods=["POST"])
def merge_sources():
    """
    Merge multiple lead sources into one canonical source.

    This operation:
    - Creates aliases for the non-canonical source names
    - Updates all leads with merged source names to use the canonical name
    - Deactivates the merged (non-canonical) source settings

    Body:
        - source_ids: List of source IDs to merge (must include canonical_source_id)
        - canonical_source_id: The ID of the source to keep as canonical
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    source_ids = data.get("source_ids")
    canonical_source_id = data.get("canonical_source_id")

    if not source_ids or not isinstance(source_ids, list):
        return jsonify({"error": "source_ids must be a non-empty list"}), 400

    if len(source_ids) < 2:
        return jsonify({"error": "At least 2 source_ids are required for merging"}), 400

    if not canonical_source_id:
        return jsonify({"error": "canonical_source_id is required"}), 400

    if canonical_source_id not in source_ids:
        return jsonify({"error": "canonical_source_id must be in source_ids"}), 400

    try:
        mapping_service = LeadSourceMappingSingleton.get_instance()
        result = mapping_service.merge_sources(source_ids, canonical_source_id, user_id)

        return jsonify({"success": True, "data": result})

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error merging sources: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Resolution Endpoint (for internal use or testing)
# =============================================================================


@lead_source_mappings_bp.route("/resolve", methods=["POST"])
def resolve_source():
    """
    Resolve a source name to its canonical source.
    Useful for testing or checking if an alias exists.

    Body:
        - source_name: The source name to resolve
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required"}), 400

    source_name = data.get("source_name")
    if not source_name:
        return jsonify({"error": "source_name is required"}), 400

    try:
        mapping_service = LeadSourceMappingSingleton.get_instance()
        result = mapping_service.resolve_source_name(source_name, user_id)

        if result:
            return jsonify(
                {
                    "success": True,
                    "is_alias": True,
                    "canonical_source_id": result["canonical_source_id"],
                    "canonical_source_name": result["canonical_source_name"],
                }
            )
        else:
            return jsonify(
                {
                    "success": True,
                    "is_alias": False,
                    "message": "No alias found for this source name",
                }
            )

    except Exception as e:
        logger.error(f"Error resolving source: {e}")
        return jsonify({"error": str(e)}), 500
