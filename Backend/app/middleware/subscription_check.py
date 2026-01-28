"""
Subscription Check Middleware - Enforces active subscription for paid features.
"""

import logging
from functools import wraps
from flask import request, jsonify

from app.database.supabase_client import SupabaseClientSingleton

logger = logging.getLogger(__name__)


def require_active_subscription(f):
    """
    Decorator to enforce that the user has an active or trialing subscription.

    Use this on endpoints that require a paid subscription to access,
    such as lead enrichment, AI features, etc.

    Returns 402 Payment Required if subscription is not active.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = request.headers.get('X-User-ID')

        if not user_id:
            return jsonify({
                "error": "Authentication required",
                "code": "auth_required"
            }), 401

        try:
            supabase = SupabaseClientSingleton.get_instance()

            # Get user's organization
            org_result = supabase.table('organization_users').select(
                'organization_id'
            ).eq('user_id', user_id).limit(1).execute()

            if not org_result.data:
                logger.warning(f"No organization found for user {user_id}")
                return jsonify({
                    "error": "No organization found",
                    "code": "no_organization"
                }), 403

            organization_id = org_result.data[0]['organization_id']

            # Check subscription status
            subscription = supabase.table('subscriptions').select(
                'status, trial_end'
            ).eq('organization_id', organization_id).limit(1).execute()

            if not subscription.data:
                logger.warning(f"No subscription found for org {organization_id}")
                return jsonify({
                    "error": "No subscription found",
                    "code": "no_subscription",
                    "message": "Please subscribe to access this feature"
                }), 402

            status = subscription.data[0]['status']

            # Allow access for active or trialing subscriptions
            if status in ['active', 'trialing']:
                return f(*args, **kwargs)

            # Subscription exists but is not active
            logger.info(f"Subscription status '{status}' for org {organization_id} - access denied")
            return jsonify({
                "error": "Active subscription required",
                "code": "subscription_inactive",
                "subscription_status": status,
                "message": "Your subscription is not active. Please update your payment method."
            }), 402

        except Exception as e:
            logger.error(f"Error checking subscription status: {e}")
            # On error, allow access to avoid blocking legitimate users
            return f(*args, **kwargs)

    return decorated


def check_subscription_status(user_id: str) -> dict:
    """
    Check the subscription status for a user.

    Args:
        user_id: The user's ID

    Returns:
        Dict with status info:
        {
            "has_subscription": bool,
            "status": "active" | "trialing" | "past_due" | "canceled" | None,
            "is_active": bool,
            "trial_end": datetime string or None,
            "organization_id": str or None
        }
    """
    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Get user's organization
        org_result = supabase.table('organization_users').select(
            'organization_id'
        ).eq('user_id', user_id).limit(1).execute()

        if not org_result.data:
            return {
                "has_subscription": False,
                "status": None,
                "is_active": False,
                "trial_end": None,
                "organization_id": None
            }

        organization_id = org_result.data[0]['organization_id']

        # Check subscription status
        subscription = supabase.table('subscriptions').select(
            'status, trial_end, current_period_end'
        ).eq('organization_id', organization_id).limit(1).execute()

        if not subscription.data:
            return {
                "has_subscription": False,
                "status": None,
                "is_active": False,
                "trial_end": None,
                "organization_id": organization_id
            }

        sub = subscription.data[0]
        status = sub['status']

        return {
            "has_subscription": True,
            "status": status,
            "is_active": status in ['active', 'trialing'],
            "trial_end": sub.get('trial_end'),
            "current_period_end": sub.get('current_period_end'),
            "organization_id": organization_id
        }

    except Exception as e:
        logger.error(f"Error checking subscription status for user {user_id}: {e}")
        return {
            "has_subscription": False,
            "status": None,
            "is_active": False,
            "error": str(e)
        }
