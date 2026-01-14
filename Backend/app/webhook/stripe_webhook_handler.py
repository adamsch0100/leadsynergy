# backend/app/webhooks/stripe_webhook_handler.py

import stripe
import os
import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify

from app.database.supabase_client import SupabaseClientSingleton

stripe_webhook = Blueprint("stripe_webhook", __name__, url_prefix="/webhooks/stripe")

logger = logging.getLogger(__name__)
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")


@stripe_webhook.route("/", methods=["POST"])
def handle_webhook():
    signature = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload=request.data, sig_header=signature, secret=webhook_secret
        )
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {str(e)}")
        return jsonify({"success": False, "error": "Invalid signature"}), 400

    # Handle different event types
    try:
        event_type = event["type"]
        event_data = event["data"]["object"]

        logger.info(f"Processing Stripe event: {event_type}")

        supabase = SupabaseClientSingleton.get_instance()

        if event_type == "customer.subscription.created":
            handle_subscription_created(supabase, event_data)
        elif event_type == "customer.subscription.updated":
            handle_subscription_updated(supabase, event_data)
        elif event_type == "customer.subscription.deleted":
            handle_subscription_deleted(supabase, event_data)
        elif event_type == "invoice.payment_succeeded":
            handle_invoice_payment_succeeded(supabase, event_data)
        elif event_type == "invoice.payment_failed":
            handle_invoice_payment_failed(supabase, event_data)
        elif event_type == "payment_method.attached":
            handle_payment_method_attached(supabase, event_data)
        elif event_type == "payment_method.detached":
            handle_payment_method_detached(supabase, event_data)
        elif event_type == "checkout.session.completed":
            handle_checkout_session_completed(supabase, event_data)

        return jsonify({"success": True}), 200
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


def handle_subscription_created(supabase, data):
    # Get organization ID from metadata
    org_id = data.get("metadata", {}).get("organization_id")
    if not org_id:
        # Try to find by customer ID
        result = (
            supabase.table("subscriptions")
            .select("organization_id")
            .eq("stripe_customer_id", data["customer"])
            .limit(1)
            .execute()
        )
        if result.data:
            org_id = result.data[0]["organization_id"]
        else:
            logger.error("Could not determine organization for subscription")
            return

    # Get plan details
    plan_id = None
    price_id = data["items"]["data"][0]["price"]["id"]
    plan_result = (
        supabase.table("subscription_plans")
        .select("id")
        .eq("stripe_price_id", price_id)
        .limit(1)
        .execute()
    )
    if plan_result.data:
        plan_id = plan_result.data[0]["id"]

    # Insert subscription record
    subscription_data = {
        "organization_id": org_id,
        "stripe_customer_id": data["customer"],
        "stripe_subscription_id": data["id"],
        "plan_id": plan_id,
        "status": data["status"],
        "current_period_start": datetime.fromtimestamp(
            data["current_period_start"]
        ).isoformat(),
        "current_period_end": datetime.fromtimestamp(
            data["current_period_end"]
        ).isoformat(),
        "cancel_at_period_end": data["cancel_at_period_end"],
        "trial_end": (
            datetime.fromtimestamp(data["trial_end"]).isoformat()
            if data.get("trial_end")
            else None
        ),
    }

    supabase.table("subscriptions").insert(subscription_data).execute()

    # Update usage limits based on plan
    if plan_id:
        plan_details = (
            supabase.table("subscription_plans")
            .select("limits")
            .eq("id", plan_id)
            .limit(1)
            .execute()
        )
        if plan_details.data:
            limits = plan_details.data[0]["limits"]

            # Update or create usage records
            for metric, limit in limits.items():
                usage_data = {
                    "organization_id": org_id,
                    "metric_name": metric,
                    "limit_value": limit,
                    "current_value": 0,
                }

                # Check if record exists
                existing = (
                    supabase.table("subscription_usage")
                    .select("id")
                    .eq("organization_id", org_id)
                    .eq("metric_name", metric)
                    .limit(1)
                    .execute()
                )

                if existing.data:
                    supabase.table("subscription_usage").update(
                        {"limit_value": limit, "updated_at": "now()"}
                    ).eq("id", existing.data[0]["id"]).execute()
                else:
                    supabase.table("subscription_usage").insert(usage_data).execute()


def handle_subscription_updated(supabase, data):
    # Update existing subscription
    subscription_data = {
        "status": data["status"],
        "current_period_start": datetime.fromtimestamp(
            data["current_period_start"]
        ).isoformat(),
        "current_period_end": datetime.fromtimestamp(
            data["current_period_end"]
        ).isoformat(),
        "cancel_at_period_end": data["cancel_at_period_end"],
        "trial_end": (
            datetime.fromtimestamp(data["trial_end"]).isoformat()
            if data.get("trial_end")
            else None
        ),
        "updated_at": "now()",
    }

    # Check if plan changed
    price_id = data["items"]["data"][0]["price"]["id"]
    plan_result = (
        supabase.table("subscription_plans")
        .select("id")
        .eq("stripe_price_id", price_id)
        .limit(1)
        .execute()
    )

    if plan_result.data:
        subscription_data["plan_id"] = plan_result.data[0]["id"]

    supabase.table("subscriptions").update(subscription_data).eq(
        "stripe_subscription_id", data["id"]
    ).execute()

    # If plan changed, update usage limits
    if plan_result.data:
        plan_id = plan_result.data[0]["id"]
        plan_details = (
            supabase.table("subscription_plans")
            .select("limits")
            .eq("id", plan_id)
            .limit(1)
            .execute()
        )

        if plan_details.data:
            limits = plan_details.data[0]["limits"]

            # Get organization ID
            org_result = (
                supabase.table("subscriptions")
                .select("organization_id")
                .eq("stripe_subscription_id", data["id"])
                .limit(1)
                .execute()
            )

            if org_result.data:
                org_id = org_result.data[0]["organization_id"]

                # Update usage limits
                for metric, limit in limits.items():
                    # Check if record exists
                    existing = (
                        supabase.table("subscription_usage")
                        .select("id")
                        .eq("organization_id", org_id)
                        .eq("metric_name", metric)
                        .limit(1)
                        .execute()
                    )

                    if existing.data:
                        supabase.table("subscription_usage").update(
                            {"limit_value": limit, "updated_at": "now()"}
                        ).eq("id", existing.data[0]["id"]).execute()
                    else:
                        supabase.table("subscription_usage").insert(
                            {
                                "organization_id": org_id,
                                "metric_name": metric,
                                "limit_value": limit,
                                "current_value": 0,
                            }
                        ).execute()


def handle_subscription_deleted(supabase, data):
    # Update subscription status
    supabase.table("subscriptions").update(
        {"status": "canceled", "updated_at": "now()"}
    ).eq("stripe_subscription_id", data["id"]).execute()


def handle_invoice_payment_succeeded(supabase, data):
    # Create or update invoice record
    invoice_data = {
        "stripe_invoice_id": data["id"],
        "stripe_payment_intent_id": data.get("payment_intent"),
        "amount_due": data["amount_due"] / 100,  # Convert from cents
        "amount_paid": data["amount_paid"] / 100,  # Convert from cents
        "currency": data["currency"],
        "status": data["status"],
        "description": data.get("description", f"Invoice {data['number']}"),
        "invoice_pdf": data.get("invoice_pdf"),
        "invoice_date": datetime.fromtimestamp(data["created"]).isoformat(),
    }

    # Get organization ID from customer
    customer_id = data["customer"]
    org_result = (
        supabase.table("subscriptions")
        .select("organization_id")
        .eq("stripe_customer_id", customer_id)
        .limit(1)
        .execute()
    )

    if not org_result.data:
        logger.error(f"Could not find organization for customer {customer_id}")
        return

    invoice_data["organization_id"] = org_result.data[0]["organization_id"]

    # Check if invoice already exists
    existing = (
        supabase.table("invoices")
        .select("id")
        .eq("stripe_invoice_id", data["id"])
        .limit(1)
        .execute()
    )

    if existing.data:
        supabase.table("invoices").update(invoice_data).eq(
            "id", existing.data[0]["id"]
        ).execute()
    else:
        supabase.table("invoices").insert(invoice_data).execute()


def handle_invoice_payment_failed(supabase, data):
    # Update invoice status
    invoice_data = {"status": "failed", "updated_at": "now()"}

    supabase.table("invoices").update(invoice_data).eq(
        "stripe_invoice_id", data["id"]
    ).execute()

    # If this is a subscription invoice, update subscription status
    if data.get("subscription"):
        supabase.table("subscriptions").update(
            {"status": "past_due", "updated_at": "now()"}
        ).eq("stripe_subscription_id", data["subscription"]).execute()


def handle_payment_method_attached(supabase, data):
    # Get organization from customer
    customer_id = data["customer"]
    payment_method_id = data["id"]

    logger.info(f"💳 Processing payment method attached webhook")
    logger.info(f"👤 Customer ID: {customer_id}")
    logger.info(f"💳 Payment Method ID: {payment_method_id}")
    logger.info(f"💳 Payment Method Type: {data.get('type')}")

    org_result = (
        supabase.table("subscriptions")
        .select("organization_id")
        .eq("stripe_customer_id", customer_id)
        .limit(1)
        .execute()
    )

    if not org_result.data:
        logger.error(f"❌ Could not find organization for customer {customer_id}")
        logger.error(
            f"❌ Available subscriptions: {supabase.table('subscriptions').select('stripe_customer_id, organization_id').execute().data}"
        )
        return

    org_id = org_result.data[0]["organization_id"]
    logger.info(f"🏢 Found organization: {org_id}")

    # Check if this payment method already exists
    existing = (
        supabase.table("payment_methods")
        .select("id")
        .eq("stripe_payment_method_id", payment_method_id)
        .limit(1)
        .execute()
    )

    if existing.data:
        logger.info(f"✅ Payment method {payment_method_id} already exists in database")
        return

    # Determine if this should be the default
    make_default = False
    existing_methods = (
        supabase.table("payment_methods")
        .select("count")
        .eq("organization_id", org_id)
        .execute()
    )

    if not existing_methods.data or len(existing_methods.data) == 0:
        make_default = True
        logger.info(
            f"🎯 Setting as default payment method (first one for organization)"
        )
    else:
        logger.info(
            f"📋 Not setting as default (organization has {len(existing_methods.data)} existing methods)"
        )

    # Create payment method record
    payment_data = {
        "organization_id": org_id,
        "stripe_payment_method_id": payment_method_id,
        "stripe_customer_id": customer_id,
        "type": data.get("type", "card"),
        "is_default": make_default,
    }

    # Add card-specific data if available
    if data.get("type") == "card" and data.get("card"):
        card = data["card"]
        payment_data.update(
            {
                "card_brand": card["brand"],
                "last_four": card["last4"],
                "expiry_month": card["exp_month"],
                "expiry_year": card["exp_year"],
            }
        )
        logger.info(f"💳 Added card details: {card['brand']} ending in {card['last4']}")

    # Add billing details if available
    if data.get("billing_details"):
        payment_data["billing_details"] = data["billing_details"]
        logger.info(f"📋 Added billing details: {data['billing_details']}")

    logger.info(f"💾 Inserting payment method data: {payment_data}")

    try:
        result = supabase.table("payment_methods").insert(payment_data).execute()
        if result.data:
            logger.info(
                f"✅ Payment method saved successfully with ID: {result.data[0].get('id')}"
            )
            logger.info(f"📊 Saved data: {result.data[0]}")
        else:
            logger.error(f"❌ Failed to save payment method - no data returned")
            logger.error(f"❌ Supabase response: {result}")
    except Exception as e:
        logger.error(f"💥 Error saving payment method to database: {str(e)}")
        logger.error(f"💥 Full error details: {e.__class__.__name__}: {str(e)}")


def handle_payment_method_detached(supabase, data):
    # Delete payment method from database
    payment_method_id = data["id"]
    customer_id = data.get("customer")

    logger.info(f"🗑️ Processing payment method detached webhook")
    logger.info(f"💳 Payment Method ID: {payment_method_id}")
    logger.info(f"👤 Customer ID: {customer_id}")

    # First, check if the payment method exists
    existing = (
        supabase.table("payment_methods")
        .select("*")
        .eq("stripe_payment_method_id", payment_method_id)
        .limit(1)
        .execute()
    )

    if not existing.data:
        logger.warning(f"⚠️ Payment method {payment_method_id} not found in database")
        return

    payment_method_info = existing.data[0]
    logger.info(f"🔍 Found payment method in database: {payment_method_info}")

    try:
        result = (
            supabase.table("payment_methods")
            .delete()
            .eq("stripe_payment_method_id", payment_method_id)
            .execute()
        )

        if result.data:
            logger.info(f"✅ Payment method {payment_method_id} deleted successfully")
            logger.info(f"📊 Deleted data: {result.data}")
        else:
            logger.warning(
                f"⚠️ Payment method {payment_method_id} deletion completed but no data returned"
            )
    except Exception as e:
        logger.error(f"💥 Error deleting payment method from database: {str(e)}")
        logger.error(f"💥 Full error details: {e.__class__.__name__}: {str(e)}")


def handle_checkout_session_completed(supabase, data):
    """
    Handle completed checkout sessions for credit bundle purchases.

    This is called when a user completes a checkout session created
    via the /api/billing/purchase-bundle endpoint.
    """
    metadata = data.get("metadata", {})

    # Check if this is a credit bundle purchase
    if metadata.get("type") != "credit_bundle_purchase":
        logger.info(f"Ignoring checkout.session.completed - not a bundle purchase")
        return

    user_id = metadata.get("user_id")
    bundle_id = metadata.get("bundle_id")

    if not user_id or not bundle_id:
        logger.error(f"Missing user_id or bundle_id in checkout session metadata")
        return

    logger.info(f"Processing credit bundle purchase for user {user_id}, bundle {bundle_id}")

    try:
        # Get the bundle details
        bundle_result = supabase.table("credit_bundles").select("*").eq("id", bundle_id).single().execute()

        if not bundle_result.data:
            logger.error(f"Bundle {bundle_id} not found")
            return

        bundle = bundle_result.data

        # Get current user credits
        user_result = supabase.table("users").select(
            "bundle_enhancement_credits, bundle_criminal_credits, bundle_dnc_credits"
        ).eq("id", user_id).single().execute()

        if not user_result.data:
            logger.error(f"User {user_id} not found")
            return

        user = user_result.data

        # Calculate new credit totals
        new_enhancement = (user.get("bundle_enhancement_credits") or 0) + (bundle.get("enhancement_credits") or 0)
        new_criminal = (user.get("bundle_criminal_credits") or 0) + (bundle.get("criminal_credits") or 0)
        new_dnc = (user.get("bundle_dnc_credits") or 0) + (bundle.get("dnc_credits") or 0)

        # Update user credits
        supabase.table("users").update({
            "bundle_enhancement_credits": new_enhancement,
            "bundle_criminal_credits": new_criminal,
            "bundle_dnc_credits": new_dnc,
        }).eq("id", user_id).execute()

        # Record the transaction
        transaction_data = {
            "user_id": user_id,
            "bundle_id": int(bundle_id),
            "transaction_type": "purchase",
            "enhancement_credits": bundle.get("enhancement_credits") or 0,
            "criminal_credits": bundle.get("criminal_credits") or 0,
            "dnc_credits": bundle.get("dnc_credits") or 0,
            "amount": data.get("amount_total", 0),
            "currency": data.get("currency", "usd").upper(),
            "credit_source": "bundle_purchase",
            "description": f"Purchased {bundle.get('name')}",
            "status": "completed",
            "stripe_session_id": data.get("id"),
        }

        supabase.table("credit_transactions").insert(transaction_data).execute()

        logger.info(f"Successfully added credits for user {user_id}: "
                   f"+{bundle.get('enhancement_credits', 0)} enhancement, "
                   f"+{bundle.get('criminal_credits', 0)} criminal, "
                   f"+{bundle.get('dnc_credits', 0)} DNC")

    except Exception as e:
        logger.error(f"Error processing bundle purchase: {str(e)}")
        raise


def register_stripe_webhook(app):
    app.register_blueprint(stripe_webhook)
