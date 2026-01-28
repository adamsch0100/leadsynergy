import os
import stripe
from dotenv import load_dotenv
from flask import request, jsonify
import logging
from datetime import datetime
from app.database.supabase_client import SupabaseClientSingleton
import stripe.error
import stripe.webhook

load_dotenv()

# Initialize Stripe with your API key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
logger = logging.getLogger(__name__)
supabase = SupabaseClientSingleton.get_instance()


def create_checkout_session():
    try:
        data = request.json
        price_id = data.get("priceId")
        organization_id = data.get("organizationId")
        customer_email = data.get("customerEmail")

        logger.info(
            f"🚀 Starting checkout session creation for organization: {organization_id}"
        )
        logger.info(f"📧 Customer email: {customer_email}")
        logger.info(f"💰 Price ID: {price_id}")

        if not price_id:
            logger.error("❌ No price ID provided")
            return jsonify({"ok": False, "error": "Price ID is required"}), 400

        # Create or get customer
        customer = None
        if customer_email:
            logger.info(f"👤 Creating/finding customer for email: {customer_email}")
            try:
                # Check if customer already exists
                customers = stripe.Customer.list(email=customer_email, limit=1)
                if customers.data:
                    customer = customers.data[0]
                    logger.info(f"✅ Found existing customer: {customer.id}")
                else:
                    # Create new customer
                    customer = stripe.Customer.create(
                        email=customer_email,
                        metadata={"organization_id": organization_id},
                    )
                    logger.info(f"✅ Created new customer: {customer.id}")
            except Exception as e:
                logger.error(f"❌ Error creating/finding customer: {str(e)}")
                return (
                    jsonify(
                        {"ok": False, "error": f"Customer creation failed: {str(e)}"}
                    ),
                    500,
                )
        else:
            logger.warning(
                "⚠️ No customer email provided - payment method may not be saved properly"
            )

        # Trial configuration
        TRIAL_PERIOD_DAYS = 3

        session_params = {
            "payment_method_types": ["card"],
            "line_items": [{"price": price_id, "quantity": 1}],
            "mode": "subscription",
            "subscription_data": {
                "trial_period_days": TRIAL_PERIOD_DAYS,
                "metadata": {"organization_id": organization_id}
            },
            "success_url": f"{os.environ.get('FRONTEND_URL')}/signup/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{os.environ.get('FRONTEND_URL')}/signup/billing/cancel",
            "metadata": {"organization_id": organization_id},
            "saved_payment_method_options": {"payment_method_save": "enabled"},
        }

        logger.info(f"🎁 Trial period: {TRIAL_PERIOD_DAYS} days")

        # Add customer to session if created
        if customer:
            session_params["customer"] = customer.id
            session_params["client_reference_id"] = organization_id
            logger.info(f"✅ Added customer {customer.id} to session params")
        else:
            logger.warning(
                "⚠️ No customer added to session - this may prevent payment method saving"
            )

        logger.info(f"🔧 Session params: {session_params}")

        session = stripe.checkout.Session.create(**session_params)

        logger.info(f"✅ Checkout session created successfully: {session.id}")
        logger.info(f"🔗 Session URL: {session.url}")

        # Log important session details
        logger.info(f"📝 Session details:")
        logger.info(f"   - Customer ID: {session.customer}")
        logger.info(f"   - Client Reference ID: {session.client_reference_id}")
        logger.info(
            f"   - Payment Method Collection: {session.payment_method_collection}"
        )
        logger.info(f"   - Mode: {session.mode}")

        return jsonify({"ok": True, "session_id": session.id})
    except Exception as e:
        logger.error(f"💥 Error creating checkout session: {str(e)}")
        logger.error(f"💥 Full error details: {e.__class__.__name__}: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


def stripe_webhook_handler():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.environ.get("STRIPE_WEBHOOK_SECRET")
        )
    except ValueError as e:
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError as e:
        return jsonify({"error": "Invalid signature"}), 400

    # Handle specific event types
    event_type = event["type"]

    if event_type == "payment_intent.payment_failed":
        return _handle_payment_failed(event)
    elif event_type == "checkout.session.completed":
        return _handle_checkout_completed(event)
    elif event_type == "invoice.paid":
        return _handle_invoice_paid(event)
    elif event_type == "invoice.payment_failed":
        return _handle_payment_failed(event)

    return jsonify({"status": "success"})


def _handle_checkout_completed(event):
    session = event["data"]["object"]
    organization_id = session.get("client_reference_id") or session.metadata.get(
        "organization_id"
    )

    logger.info(f"🎉 Processing checkout completion webhook")
    logger.info(f"🏢 Organization ID: {organization_id}")
    logger.info(f"💳 Session ID: {session.get('id')}")

    if not organization_id:
        logger.error("❌ No organization ID found in checkout session")
        logger.error(f'Session metadata: {session.get("metadata", {})}')
        logger.error(f'Client reference ID: {session.get("client_reference_id")}')
        return jsonify({"error": "No organization ID found"}), 400

    try:
        # Get the subscription associated with the checkout
        subscription_id = session.subscription
        customer_id = session.customer

        logger.info(f"📧 Customer ID: {customer_id}")
        logger.info(f"📋 Subscription ID: {subscription_id}")

        if not subscription_id:
            logger.error("❌ No subscription ID found in checkout session")
            return jsonify({"error": "No subscription ID found"}), 400

        subscription = stripe.Subscription.retrieve(subscription_id)
        logger.info(f"✅ Retrieved subscription: {subscription.id}")

        # Get customer details
        if customer_id:
            customer = stripe.Customer.retrieve(customer_id)
            logger.info(f"✅ Retrieved customer: {customer.id} ({customer.email})")

            # Get the payment method used for this subscription
            if subscription.default_payment_method:
                payment_method_id = subscription.default_payment_method
                logger.info(f"💳 Default payment method: {payment_method_id}")

                try:
                    payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
                    logger.info(f"✅ Retrieved payment method: {payment_method.id}")
                    logger.info(f"💳 Payment method type: {payment_method.type}")

                    if payment_method.type == "card":
                        card = payment_method.card
                        logger.info(
                            f"💳 Card details: {card.brand} ending in {card.last4}"
                        )
                        logger.info(f"💳 Expiry: {card.exp_month}/{card.exp_year}")

                    # Save payment method to database
                    success = _save_payment_method_to_db(
                        payment_method, customer_id, organization_id
                    )
                    if success:
                        logger.info("✅ Payment method saved to database successfully")
                    else:
                        logger.error("❌ Failed to save payment method to database")

                except Exception as pm_error:
                    logger.error(
                        f"❌ Error retrieving payment method {payment_method_id}: {str(pm_error)}"
                    )
            else:
                logger.warning(
                    f"⚠️ No default payment method found for subscription {subscription_id}"
                )
        else:
            logger.warning("⚠️ No customer ID found in session")

        # Determine the subscription plan based on price ID
        price_id = subscription.items.data[0].price.id
        plan = _determine_plan_from_price(price_id)
        logger.info(f"📋 Determined plan: {plan} from price ID: {price_id}")

        # Calculate subscription end date
        end_date = datetime.fromtimestamp(subscription.current_period_end)
        logger.info(f"📅 Subscription end date: {end_date}")

        # Check if this is a trial subscription and grant credits
        if subscription.status == "trialing" and subscription.trial_end:
            logger.info(f"🎁 Subscription is in trial status, granting trial credits")
            trial_end = datetime.fromtimestamp(subscription.trial_end)
            logger.info(f"📅 Trial ends at: {trial_end}")

            # Get primary user for this organization to grant credits
            try:
                user_result = supabase.table('organization_users').select(
                    'user_id'
                ).eq('organization_id', organization_id).limit(1).execute()

                if user_result.data:
                    user_id = user_result.data[0]['user_id']
                    logger.info(f"👤 Found primary user {user_id} for org {organization_id}")

                    # Grant trial credits
                    from app.service.trial_service import TrialServiceSingleton
                    trial_service = TrialServiceSingleton.get_instance()
                    grant_result = trial_service.grant_trial_credits(user_id, trial_end)

                    if grant_result.get('success'):
                        logger.info(f"✅ Trial credits granted to user {user_id}")
                    else:
                        logger.error(f"❌ Failed to grant trial credits: {grant_result.get('error')}")
                else:
                    logger.warning(f"⚠️ No users found for organization {organization_id}")
            except Exception as trial_error:
                logger.error(f"❌ Error granting trial credits: {trial_error}")

        # Update organization subscription status in the database
        # Use 'trialing' status if subscription is in trial, otherwise 'active'
        subscription_status = "trialing" if subscription.status == "trialing" else "active"

        update_data = {
            "subscription_status": subscription_status,
            "subscription_plan": plan,
            "stripe_customer_id": customer_id,
            "subscription_end_date": end_date.isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        logger.info(
            f"💾 Updating organization {organization_id} with data: {update_data}"
        )

        result = (
            supabase.table("organizations")
            .update(update_data)
            .eq("id", organization_id)
            .execute()
        )

        if not result.data or len(result.data) == 0:
            logger.error(
                f"❌ Organization with ID {organization_id} not found in database"
            )
            return jsonify({"error": "Organization not found"}), 400

        logger.info(
            f"✅ Successfully updated subscription for organization {organization_id}"
        )
        logger.info(f"📊 Database update result: {result.data}")

        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"💥 Error handling checkout completion: {str(e)}")
        logger.error(f"💥 Full error details: {e.__class__.__name__}: {str(e)}")
        return jsonify({"error": "Error processing checkout"}), 500


def _save_payment_method_to_db(payment_method, customer_id, organization_id):
    """Save payment method details to the database with comprehensive logging"""
    try:
        logger.info(f"💾 Saving payment method {payment_method.id} to database")
        logger.info(f"🏢 Organization ID: {organization_id}")
        logger.info(f"👤 Customer ID: {customer_id}")

        payment_method_data = {
            "organization_id": organization_id,
            "stripe_payment_method_id": payment_method.id,
            "stripe_customer_id": customer_id,
            "type": payment_method.type,
            "is_default": True,  # First payment method is default
        }

        if payment_method.type == "card":
            card = payment_method.card
            payment_method_data.update(
                {
                    "card_brand": card.brand,
                    "last_four": card.last4,
                    "expiry_month": card.exp_month,
                    "expiry_year": card.exp_year,
                }
            )
            logger.info(f"💳 Card data added: {card.brand} ending in {card.last4}")

        # Store billing details
        if payment_method.billing_details:
            payment_method_data["billing_details"] = payment_method.billing_details
            logger.info(f"📋 Billing details added: {payment_method.billing_details}")

        logger.info(f"💾 Payment method data to save: {payment_method_data}")

        # Insert into database
        result = supabase.table("payment_methods").insert(payment_method_data).execute()

        if result.data:
            logger.info(
                f"✅ Payment method saved successfully with ID: {result.data[0].get('id')}"
            )
            logger.info(f"📊 Saved data: {result.data[0]}")
            return True
        else:
            logger.error(f"❌ Failed to save payment method - no data returned")
            logger.error(f"❌ Supabase response: {result}")
            return False

    except Exception as e:
        logger.error(f"💥 Error saving payment method to database: {str(e)}")
        logger.error(f"💥 Full error details: {e.__class__.__name__}: {str(e)}")
        return False


def _handle_invoice_paid(event):
    invoice = event["data"]["object"]
    subscription_id = invoice.get("subscription")

    if not subscription_id:
        logger.error("No subcscription ID found in invoice")
        return jsonify({"error": "No subcscription ID found"}), 400

    try:
        # Get subscription details
        subscription = stripe.Subscription.retrieve(subscription_id)

        # Get the organization ID from subscription metadata
        customer = stripe.Customer.retrieve(subscription.customer)
        organization_id = None

        # Try to find organization_id from subscription metadata
        if hasattr(subscription, "metadata") and subscription.metadata.get(
            "organization_id"
        ):
            organization_id = subscription.metadata.get("organization_id")
        elif hasattr(customer, "metadata") and customer.metadata.get("organization_id"):
            organization_id = customer.metadata.get("organization_id")

        if not organization_id:
            logger.error(
                "No organization ID found in subscription or customer metadata"
            )
            return jsonify({"error": "No organization ID found"}), 400

        # Calculate new subscription end date
        end_date = datetime.fromtimestamp(subscription.current_period_end).isoformat()

        # Update organization subcscription status in Supabase
        result = (
            supabase.table("organizations")
            .update(
                {
                    "subscription_status": "active",
                    "subcscription_end_date": end_date,
                    "updated_at": datetime.now().isoformat(),
                }
            )
            .eq("id", organization_id)
            .execute()
        )

        if not result.data or len(result.data) == 0:
            logger.error(f"Organization with ID {organization_id} not found")
            return jsonify({"error": "Organization not found"}), 404

        logger.info(
            f"Successfullly renewed subcscription for organization {organization_id}"
        )
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error handling invoice payment: {str(e)}")
        return jsonify({"error": "Error processing invoice payment"}), 500


def _handle_payment_failed(event):
    invoice = event["data"]["object"]
    subscription_id = invoice.get("subscription")

    if not subscription_id:
        logger.error("No subcscription ID found in failed invoice")
        return jsonify({"error": "No subcscription ID found"}), 400

    try:
        # Get subcscription details
        subscription = stripe.Subscription.retrieve(subscription_id)

        # Get the organization ID from subscription metadata
        customer = stripe.Customer.retrieve(subscription.customer)
        organization_id = None

        # Try to find organization_id from subscription metadata or customer metadata
        if hasattr(subscription, "metadata") and subscription.metadata.get(
            "organization_id"
        ):
            organization_id = subscription.metadata.get("organization_id")
        elif hasattr(customer, "metadata") and customer.metadata.get("organization_id"):
            organization_id = customer.metadata.get("organization_id")

        if not organization_id:
            logger.error(
                "No organization ID found in subcscription or customer metadata"
            )
            return jsonify({"error": "No organization ID found"}), 400

        # Update organization subcscription status in Supabase
        result = (
            supabase.table("organizations")
            .update(
                {
                    "subscription_status": "past_due",
                    "updated_at": datetime.now().isoformat(),
                }
            )
            .eq("id", organization_id)
            .execute()
        )

        if not result.data or len(result.data) == 0:
            logger.error(f"Organization with ID {organization_id} not found")
            return jsonify({"error": "Organization not found"}), 404

        logger.info(
            f"Marked subcscription as past_due for organization {organization_id}"
        )
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error handling payment failure: {str(e)}")
        return jsonify({"error": "Error processing payment failure"})


def _determine_plan_from_price(price_id):
    """
    Map Stripe price IDs to plan names.

    Supports both modular pricing structure and legacy plans:
    - Base Platform Plans: starter, growth, pro, enterprise
    - Enhancement Plans: enhance-starter, enhance-growth, enhance-pro
    - Legacy Plans: solo, team, brokerage, enterprise (backward compatibility)
    """
    # NEW MODULAR STRUCTURE - Base Platform Plans
    base_platform_plans = {
        os.getenv("STRIPE_PRICE_STARTER", "price_starter"): "starter",
        os.getenv("STRIPE_PRICE_GROWTH", "price_growth"): "growth",
        os.getenv("STRIPE_PRICE_PRO", "price_pro"): "pro",
        os.getenv("STRIPE_PRICE_BASE_ENTERPRISE", "price_base_enterprise"): "enterprise",
    }

    # NEW MODULAR STRUCTURE - Enhancement Plans
    enhancement_plans = {
        os.getenv("STRIPE_PRICE_ENHANCE_STARTER", "price_enhance_starter"): "enhance-starter",
        os.getenv("STRIPE_PRICE_ENHANCE_GROWTH", "price_enhance_growth"): "enhance-growth",
        os.getenv("STRIPE_PRICE_ENHANCE_PRO", "price_enhance_pro"): "enhance-pro",
    }

    # LEGACY PLANS (backward compatibility)
    legacy_plans = {
        os.getenv("STRIPE_PRICE_SOLO", "price_solo"): "solo",
        os.getenv("STRIPE_PRICE_TEAM", "price_team"): "team",
        os.getenv("STRIPE_PRICE_BROKERAGE", "price_brokerage"): "brokerage",
        os.getenv("STRIPE_PRICE_ENTERPRISE", "price_enterprise"): "enterprise",
    }

    # Check new modular plans first, then legacy
    if price_id in base_platform_plans:
        return base_platform_plans[price_id]
    if price_id in enhancement_plans:
        return enhancement_plans[price_id]
    if price_id in legacy_plans:
        return legacy_plans[price_id]

    # Default to starter (new default) or solo (legacy)
    return "starter"


def _is_enhancement_plan(plan_id):
    """Check if a plan ID is an enhancement subscription."""
    return plan_id.startswith("enhance-")
