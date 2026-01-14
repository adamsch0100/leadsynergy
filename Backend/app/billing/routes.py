"""
Billing API Routes - Credit management, bundle purchases, and transactions.
"""

from flask import request, jsonify
import logging
import os
import stripe

from app.billing import billing_bp
from app.billing.credit_service import CreditServiceSingleton
from app.database.supabase_client import SupabaseClientSingleton
from app.models.credit_bundle import CreditBundle

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')


def get_user_id_from_request():
    """Extract user ID from request headers or body."""
    user_id = request.headers.get('X-User-ID')
    if not user_id and request.is_json:
        data = request.get_json(silent=True)
        if data:
            user_id = data.get('user_id')
    return user_id


# =============================================================================
# Credit Balance Endpoints
# =============================================================================

@billing_bp.route('/credits/balance', methods=['GET'])
def get_credit_balance():
    """
    Get the current credit balance for a user.

    Returns all credit pools and totals.
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        credit_service = CreditServiceSingleton.get_instance()
        credits = credit_service.get_user_credits(user_id)

        if not credits:
            return jsonify({"error": "User not found"}), 404

        return jsonify({
            "success": True,
            "credits": credits
        })

    except Exception as e:
        logger.error(f"Error getting credit balance: {e}")
        return jsonify({"error": str(e)}), 500


@billing_bp.route('/credits/can-perform', methods=['POST'])
def can_perform_search():
    """
    Check if user has enough credits to perform a search.

    Body:
        - credit_type: 'enhancement', 'criminal', or 'dnc'
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    data = request.get_json()
    credit_type = data.get('credit_type')

    if not credit_type:
        return jsonify({"error": "credit_type is required"}), 400

    if credit_type not in ['enhancement', 'criminal', 'dnc']:
        return jsonify({"error": "Invalid credit_type. Must be 'enhancement', 'criminal', or 'dnc'"}), 400

    try:
        credit_service = CreditServiceSingleton.get_instance()
        can_perform, reason = credit_service.can_perform_search(user_id, credit_type)

        return jsonify({
            "success": True,
            "can_perform": can_perform,
            "reason": reason
        })

    except Exception as e:
        logger.error(f"Error checking if can perform search: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Credit Allocation Endpoints (Broker to Agent)
# =============================================================================

@billing_bp.route('/credits/allocate', methods=['POST'])
def allocate_credits():
    """
    Allocate credits from broker to agent.

    Body:
        - agent_id: The agent's user ID
        - enhancement_credits: Number of enhancement credits (optional)
        - criminal_credits: Number of criminal credits (optional)
        - dnc_credits: Number of DNC credits (optional)
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "Broker ID is required"}), 400

    data = request.get_json()
    agent_id = data.get('agent_id')

    if not agent_id:
        return jsonify({"error": "agent_id is required"}), 400

    enhancement_credits = data.get('enhancement_credits', 0)
    criminal_credits = data.get('criminal_credits', 0)
    dnc_credits = data.get('dnc_credits', 0)

    try:
        credit_service = CreditServiceSingleton.get_instance()
        success, message = credit_service.allocate_credits(
            broker_id=user_id,
            agent_id=agent_id,
            enhancement_credits=enhancement_credits,
            criminal_credits=criminal_credits,
            dnc_credits=dnc_credits
        )

        if success:
            return jsonify({
                "success": True,
                "message": message
            })
        else:
            return jsonify({
                "success": False,
                "error": message
            }), 400

    except Exception as e:
        logger.error(f"Error allocating credits: {e}")
        return jsonify({"error": str(e)}), 500


@billing_bp.route('/credits/available-for-allocation', methods=['GET'])
def get_available_for_allocation():
    """
    Get credits available for broker to allocate (total minus already allocated).
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "Broker ID is required"}), 400

    try:
        credit_service = CreditServiceSingleton.get_instance()
        available = credit_service.get_available_credits_for_allocation(user_id)

        return jsonify({
            "success": True,
            "available": available
        })

    except Exception as e:
        logger.error(f"Error getting available credits for allocation: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Bundle Endpoints
# =============================================================================

@billing_bp.route('/bundles', methods=['GET'])
def list_bundles():
    """
    List available credit bundles for purchase.

    Query params:
        - bundle_type: 'addon' or 'subscription' (optional, filters by type)
        - include_inactive: 'true' to include inactive bundles (admin only)
    """
    try:
        supabase = SupabaseClientSingleton.get_instance()

        bundle_type = request.args.get('bundle_type')
        include_inactive = request.args.get('include_inactive', '').lower() == 'true'

        query = supabase.table('credit_bundles').select('*')

        if bundle_type:
            query = query.eq('bundle_type', bundle_type)

        if not include_inactive:
            query = query.eq('is_active', True)

        # Filter test bundles in production
        if os.environ.get('FLASK_ENV') != 'development':
            query = query.eq('is_test', False)

        result = query.order('price').execute()

        bundles = [CreditBundle.from_dict(b).to_dict() for b in (result.data or [])]

        return jsonify({
            "success": True,
            "bundles": bundles
        })

    except Exception as e:
        logger.error(f"Error listing bundles: {e}")
        return jsonify({"error": str(e)}), 500


@billing_bp.route('/bundles/<int:bundle_id>', methods=['GET'])
def get_bundle(bundle_id):
    """Get a specific bundle by ID."""
    try:
        supabase = SupabaseClientSingleton.get_instance()

        result = supabase.table('credit_bundles').select('*').eq('id', bundle_id).single().execute()

        if not result.data:
            return jsonify({"error": "Bundle not found"}), 404

        bundle = CreditBundle.from_dict(result.data)

        return jsonify({
            "success": True,
            "bundle": bundle.to_dict()
        })

    except Exception as e:
        logger.error(f"Error getting bundle: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Purchase Endpoints
# =============================================================================

@billing_bp.route('/purchase-bundle', methods=['POST'])
def purchase_bundle():
    """
    Create a Stripe checkout session to purchase a credit bundle.

    Body:
        - bundle_id: The bundle to purchase
        - success_url: URL to redirect on success (optional)
        - cancel_url: URL to redirect on cancel (optional)
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    data = request.get_json()
    bundle_id = data.get('bundle_id')

    if not bundle_id:
        return jsonify({"error": "bundle_id is required"}), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Get the bundle
        bundle_result = supabase.table('credit_bundles').select('*').eq('id', bundle_id).single().execute()

        if not bundle_result.data:
            return jsonify({"error": "Bundle not found"}), 404

        bundle = CreditBundle.from_dict(bundle_result.data)

        if not bundle.is_active:
            return jsonify({"error": "This bundle is not available for purchase"}), 400

        # Get user's Stripe customer ID (or create one)
        user_result = supabase.table('users').select('email, stripe_customer_id').eq('id', user_id).single().execute()

        if not user_result.data:
            return jsonify({"error": "User not found"}), 404

        user_email = user_result.data.get('email')
        stripe_customer_id = user_result.data.get('stripe_customer_id')

        # Create Stripe customer if needed
        if not stripe_customer_id:
            customer = stripe.Customer.create(
                email=user_email,
                metadata={
                    'user_id': user_id
                }
            )
            stripe_customer_id = customer.id

            # Save customer ID
            supabase.table('users').update({
                'stripe_customer_id': stripe_customer_id
            }).eq('id', user_id).execute()

        # Build success/cancel URLs
        frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
        success_url = data.get('success_url', f"{frontend_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}")
        cancel_url = data.get('cancel_url', f"{frontend_url}/billing/cancel")

        # Create checkout session
        if bundle.stripe_price_id:
            # Use existing Stripe price
            line_items = [{
                'price': bundle.stripe_price_id,
                'quantity': 1,
            }]
        else:
            # Create ad-hoc price
            line_items = [{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': bundle.price,
                    'product_data': {
                        'name': bundle.name,
                        'description': bundle.description or f"{bundle.total_credits} credits",
                    },
                },
                'quantity': 1,
            }]

        session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            line_items=line_items,
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'user_id': user_id,
                'bundle_id': str(bundle_id),
                'type': 'credit_bundle_purchase'
            }
        )

        logger.info(f"Created checkout session {session.id} for user {user_id}, bundle {bundle_id}")

        return jsonify({
            "success": True,
            "checkout_url": session.url,
            "session_id": session.id
        })

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {e}")
        return jsonify({"error": f"Payment error: {str(e)}"}), 400

    except Exception as e:
        logger.error(f"Error creating checkout session: {e}")
        return jsonify({"error": str(e)}), 500


@billing_bp.route('/checkout-session/<session_id>', methods=['GET'])
def get_checkout_session(session_id):
    """
    Get the status of a checkout session.
    """
    try:
        session = stripe.checkout.Session.retrieve(session_id)

        return jsonify({
            "success": True,
            "status": session.status,
            "payment_status": session.payment_status,
            "metadata": session.metadata
        })

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error retrieving session: {e}")
        return jsonify({"error": str(e)}), 400

    except Exception as e:
        logger.error(f"Error retrieving checkout session: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Transaction History Endpoints
# =============================================================================

@billing_bp.route('/transactions', methods=['GET'])
def get_transactions():
    """
    Get credit transaction history for a user.

    Query params:
        - limit: Number of transactions to return (default 50, max 100)
        - offset: Offset for pagination (default 0)
        - transaction_type: Filter by type (usage, purchase, subscription, allocation)
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))
        transaction_type = request.args.get('transaction_type')

        query = supabase.table('credit_transactions').select('*').eq('user_id', user_id)

        if transaction_type:
            query = query.eq('transaction_type', transaction_type)

        result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()

        return jsonify({
            "success": True,
            "transactions": result.data or [],
            "limit": limit,
            "offset": offset
        })

    except Exception as e:
        logger.error(f"Error getting transactions: {e}")
        return jsonify({"error": str(e)}), 500


@billing_bp.route('/transactions/summary', methods=['GET'])
def get_transaction_summary():
    """
    Get a summary of credit usage for a user.

    Query params:
        - days: Number of days to summarize (default 30)
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        from datetime import datetime, timedelta

        supabase = SupabaseClientSingleton.get_instance()

        days = int(request.args.get('days', 30))
        since_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

        # Get usage transactions
        result = supabase.table('credit_transactions').select(
            'transaction_type, enhancement_credits, criminal_credits, dnc_credits'
        ).eq('user_id', user_id).eq('transaction_type', 'usage').gte('created_at', since_date).execute()

        transactions = result.data or []

        total_enhancement_used = sum(t.get('enhancement_credits', 0) for t in transactions)
        total_criminal_used = sum(t.get('criminal_credits', 0) for t in transactions)
        total_dnc_used = sum(t.get('dnc_credits', 0) for t in transactions)

        return jsonify({
            "success": True,
            "period_days": days,
            "usage": {
                "enhancement_credits": total_enhancement_used,
                "criminal_credits": total_criminal_used,
                "dnc_credits": total_dnc_used,
                "total_searches": len(transactions)
            }
        })

    except Exception as e:
        logger.error(f"Error getting transaction summary: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# Admin Endpoints (require admin check)
# =============================================================================

@billing_bp.route('/admin/bundles', methods=['POST'])
def create_bundle():
    """
    Create a new credit bundle (admin only).

    Body:
        - name: Bundle name
        - description: Bundle description
        - price: Price in cents
        - enhancement_credits: Number of enhancement credits
        - criminal_credits: Number of criminal credits
        - dnc_credits: Number of DNC credits
        - bundle_type: 'addon' or 'subscription'
        - stripe_price_id: Stripe price ID (optional)
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Check if user is admin
        user_result = supabase.table('users').select('is_admin').eq('id', user_id).single().execute()

        if not user_result.data or not user_result.data.get('is_admin'):
            return jsonify({"error": "Admin access required"}), 403

        data = request.get_json()

        required_fields = ['name', 'price']
        for field in required_fields:
            if not data.get(field):
                return jsonify({"error": f"{field} is required"}), 400

        bundle_data = {
            'name': data['name'],
            'description': data.get('description'),
            'price': data['price'],
            'enhancement_credits': data.get('enhancement_credits', 0),
            'criminal_credits': data.get('criminal_credits', 0),
            'dnc_credits': data.get('dnc_credits', 0),
            'bundle_type': data.get('bundle_type', 'addon'),
            'stripe_price_id': data.get('stripe_price_id'),
            'is_active': data.get('is_active', True),
            'is_test': data.get('is_test', False),
        }

        result = supabase.table('credit_bundles').insert(bundle_data).execute()

        if result.data:
            return jsonify({
                "success": True,
                "bundle": result.data[0]
            })
        else:
            return jsonify({"error": "Failed to create bundle"}), 500

    except Exception as e:
        logger.error(f"Error creating bundle: {e}")
        return jsonify({"error": str(e)}), 500


@billing_bp.route('/admin/bundles/<int:bundle_id>', methods=['PUT'])
def update_bundle(bundle_id):
    """Update a credit bundle (admin only)."""
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "User ID is required"}), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Check if user is admin
        user_result = supabase.table('users').select('is_admin').eq('id', user_id).single().execute()

        if not user_result.data or not user_result.data.get('is_admin'):
            return jsonify({"error": "Admin access required"}), 403

        data = request.get_json()

        # Build update data (only include provided fields)
        update_data = {}
        allowed_fields = [
            'name', 'description', 'price', 'enhancement_credits',
            'criminal_credits', 'dnc_credits', 'bundle_type',
            'stripe_price_id', 'is_active', 'is_test'
        ]

        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]

        if not update_data:
            return jsonify({"error": "No fields to update"}), 400

        result = supabase.table('credit_bundles').update(update_data).eq('id', bundle_id).execute()

        if result.data:
            return jsonify({
                "success": True,
                "bundle": result.data[0]
            })
        else:
            return jsonify({"error": "Bundle not found or update failed"}), 404

    except Exception as e:
        logger.error(f"Error updating bundle: {e}")
        return jsonify({"error": str(e)}), 500


@billing_bp.route('/admin/add-credits', methods=['POST'])
def admin_add_credits():
    """
    Manually add credits to a user (admin only).
    Used for refunds, promotions, etc.

    Body:
        - target_user_id: The user to add credits to
        - credit_type: 'enhancement', 'criminal', or 'dnc'
        - amount: Number of credits to add
        - description: Reason for adding credits
    """
    user_id = get_user_id_from_request()
    if not user_id:
        return jsonify({"error": "Admin ID is required"}), 400

    try:
        supabase = SupabaseClientSingleton.get_instance()

        # Check if user is admin
        user_result = supabase.table('users').select('is_admin').eq('id', user_id).single().execute()

        if not user_result.data or not user_result.data.get('is_admin'):
            return jsonify({"error": "Admin access required"}), 403

        data = request.get_json()
        target_user_id = data.get('target_user_id')
        credit_type = data.get('credit_type')
        amount = data.get('amount')
        description = data.get('description', 'Manual credit adjustment by admin')

        if not target_user_id:
            return jsonify({"error": "target_user_id is required"}), 400

        if not credit_type or credit_type not in ['enhancement', 'criminal', 'dnc']:
            return jsonify({"error": "Valid credit_type is required"}), 400

        if not amount or amount <= 0:
            return jsonify({"error": "Positive amount is required"}), 400

        credit_service = CreditServiceSingleton.get_instance()
        success, message = credit_service.add_credits(
            user_id=target_user_id,
            credit_type=credit_type,
            amount=amount,
            description=f"{description} (by admin {user_id})"
        )

        if success:
            return jsonify({
                "success": True,
                "message": message
            })
        else:
            return jsonify({
                "success": False,
                "error": message
            }), 400

    except Exception as e:
        logger.error(f"Error adding credits: {e}")
        return jsonify({"error": str(e)}), 500
