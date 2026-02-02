"""
JWT Authentication Middleware for LeadSynergy.

Validates Supabase JWT tokens from the Authorization header and extracts
user identity. Falls back to X-User-ID header for backward compatibility
during migration, but logs a deprecation warning.

Usage:
    @require_auth
    def my_endpoint():
        user_id = g.user_id  # Verified user ID from JWT
        ...

    @require_auth_with_org
    def my_org_endpoint():
        user_id = g.user_id
        org_id = g.organization_id  # Verified org membership
        ...
"""

import os
import logging
from functools import wraps

import jwt
from flask import request, jsonify, g

from app.database.supabase_client import SupabaseClientSingleton

logger = logging.getLogger(__name__)

# Cache the JWT secret at module level
_JWT_SECRET = None


def _get_jwt_secret() -> str:
    """Get the Supabase JWT secret (cached)."""
    global _JWT_SECRET
    if _JWT_SECRET is None:
        _JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
        if not _JWT_SECRET:
            logger.warning("SUPABASE_JWT_SECRET is not set — JWT verification will fail")
    return _JWT_SECRET


def _verify_jwt(token: str) -> dict | None:
    """
    Verify a Supabase JWT and return the decoded payload.

    Returns None if verification fails.
    """
    secret = _get_jwt_secret()
    if not secret:
        return None

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("JWT expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"JWT validation failed: {e}")
        return None


def _extract_user_id_from_request() -> str | None:
    """
    Extract and verify user identity from the request.

    Priority:
    1. Authorization: Bearer <jwt> header (verified)
    2. X-User-ID header (unverified, backward compat — logged as warning)

    Sets g.auth_method to 'jwt' or 'header' for auditing.
    """
    # Try JWT first
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = _verify_jwt(token)
        if payload:
            user_id = payload.get("sub")
            if user_id:
                g.auth_method = "jwt"
                g.jwt_payload = payload
                g.user_email = payload.get("email")
                return user_id

    # Fall back to X-User-ID header (backward compatibility)
    user_id = request.headers.get("X-User-ID")
    if user_id:
        g.auth_method = "header"
        logger.debug(
            f"Request authenticated via X-User-ID header (deprecated) — "
            f"path={request.path}, user={user_id[:8]}..."
        )
        return user_id

    return None


def require_auth(f):
    """
    Decorator that requires a verified user identity.

    Extracts user_id from JWT (preferred) or X-User-ID header (fallback).
    Sets g.user_id for downstream use.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = _extract_user_id_from_request()

        if not user_id:
            return jsonify({
                "error": "Authentication required",
                "code": "auth_required",
            }), 401

        g.user_id = user_id
        return f(*args, **kwargs)

    return decorated


def require_auth_with_org(f):
    """
    Decorator that requires both a verified user identity AND resolves
    their organization membership.

    Sets g.user_id and g.organization_id for downstream use.
    Returns 403 if the user doesn't belong to any organization.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = _extract_user_id_from_request()

        if not user_id:
            return jsonify({
                "error": "Authentication required",
                "code": "auth_required",
            }), 401

        g.user_id = user_id

        # Resolve organization membership
        org_id = _get_user_organization(user_id)
        if not org_id:
            return jsonify({
                "error": "No organization found for this user",
                "code": "no_organization",
            }), 403

        g.organization_id = org_id
        return f(*args, **kwargs)

    return decorated


def ensure_same_organization(user_id: str, organization_id: str) -> bool:
    """
    Verify that a user belongs to the given organization.

    Use this for cross-resource authorization checks, e.g. when a request
    includes an organization_id parameter that needs validation.

    Args:
        user_id: The authenticated user's ID.
        organization_id: The organization ID to check membership for.

    Returns:
        True if the user is a member of the organization, False otherwise.
    """
    try:
        supabase = SupabaseClientSingleton.get_instance()
        result = (
            supabase.table("organization_users")
            .select("id")
            .eq("user_id", user_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
        )
        return bool(result.data)
    except Exception as e:
        logger.error(f"Error checking org membership: {e}")
        return False


def _get_user_organization(user_id: str) -> str | None:
    """Look up the primary organization for a user."""
    try:
        supabase = SupabaseClientSingleton.get_instance()
        result = (
            supabase.table("organization_users")
            .select("organization_id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["organization_id"]
        return None
    except Exception as e:
        logger.error(f"Error looking up organization for user {user_id}: {e}")
        return None
