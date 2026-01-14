import stripe
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from app.database.supabase_client import SupabaseClientSingleton
from app.models.subscription import Subscription, PaymentMethod, Invoice

# Initialize Stripe
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")


class SubscriptionService:
    def __init__(self):
        self.supabase = SupabaseClientSingleton.get_instance()
        self.logger = logging.getLogger(__name__)

    def get_subscription(self, organization_id: str) -> Dict[str, Any]:
        """Get the current subscription for an organization"""
        try:
            # Get subscription from database
            result = (
                self.supabase.table("subscriptions")
                .select("*, subscription_plans(*)")
                .eq("organization_id", organization_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            if not result.data:
                return self._get_default_subscription(organization_id)

            subscription_data = result.data[0]

            # Get usage metrics
            usage_result = (
                self.supabase.table("subscription_usage")
                .select("*")
                .eq("organization_id", organization_id)
                .execute()
            )

            usage_metrics = {}
            for metric in usage_result.data:
                usage_metrics[metric["metric_name"]] = {
                    "current": metric["current_value"],
                    "limit": metric["limit_value"],
                }

            # Format subscription data
            return {
                "id": subscription_data["id"],
                "plan": subscription_data["subscription_plans"]["name"].lower(),
                "organizationId": subscription_data["organization_id"],
                "status": subscription_data["status"],
                "trialEndsAt": subscription_data["trial_end"],
                "currentPeriodEnd": subscription_data["current_period_end"],
                "cancelAtPeriodEnd": subscription_data["cancel_at_period_end"],
                "usage": {
                    "teamMembers": usage_metrics.get(
                        "team_members", {"current": 0, "limit": 1}
                    ),
                    "leadSources": usage_metrics.get(
                        "lead_sources", {"current": 0, "limit": 1}
                    ),
                    "storage": usage_metrics.get("storage", {"current": 0, "limit": 1}),
                },
            }
        except Exception as e:
            self.logger.error(f"Error getting subscription: {str(e)}")
            return self._get_default_subscription(organization_id)

    def _get_default_subscription(self, organization_id: str) -> Dict[str, Any]:
        """Return default free subscription"""
        return {
            "plan": "free",
            "organizationId": organization_id,
            "status": "active",
            "trialEndsAt": None,
            "currentPeriodEnd": datetime.now().isoformat(),
            "cancelAtPeriodEnd": False,
            "usage": {
                "teamMembers": {"current": 0, "limit": 1},
                "leadSources": {"current": 0, "limit": 1},
                "storage": {"current": 0, "limit": 1},
            },
        }

    def get_payment_methods(self, organization_id: str) -> List[Dict[str, Any]]:
        """Get payment methods for an organization"""
        try:
            result = (
                self.supabase.table("payment_methods")
                .select("*")
                .eq("organization_id", organization_id)
                .execute()
            )

            payment_methods = []
            for pm in result.data:
                payment_methods.append(
                    {
                        "id": pm["id"],
                        "type": pm["card_brand"].lower(),
                        "lastFour": pm["last_four"],
                        "expiryDate": f"{pm['expiry_month']}/{str(pm['expiry_year'])[-2:]}",
                        "isDefault": pm["is_default"],
                    }
                )

            return payment_methods
        except Exception as e:
            self.logger.error(f"Error getting payment methods: {str(e)}")
            return []

    def get_billing_history(self, organization_id: str) -> List[Dict[str, Any]]:
        """Get billing history for an organization"""
        try:
            result = (
                self.supabase.table("invoices")
                .select("*")
                .eq("organization_id", organization_id)
                .order("invoice_date", desc=True)
                .execute()
            )

            billing_history = []
            for invoice in result.data:
                billing_history.append(
                    {
                        "id": invoice["id"],
                        "date": invoice["invoice_date"],
                        "description": invoice["description"],
                        "amount": f"${invoice['amount_paid']}",
                        "status": invoice["status"],
                        "invoiceUrl": invoice["invoice_pdf"],
                    }
                )

            return billing_history
        except Exception as e:
            self.logger.error(f"Error getting billing history: {str(e)}")
            return []

    def add_payment_method(
        self, organization_id: str, payment_method_id: str
    ) -> Dict[str, Any]:
        """Add a new payment method"""
        try:
            # Get stripe customer ID
            org_result = (
                self.supabase.table("subscriptions")
                .select("stripe_customer_id")
                .eq("organization_id", organization_id)
                .limit(1)
                .execute()
            )

            if not org_result.data:
                raise Exception("No subscription found for this organization")

            stripe_customer_id = org_result.data[0]["stripe_customer_id"]

            # Attach payment method to customer in Stripe
            payment_method = stripe.PaymentMethod.attach(
                payment_method_id, customer=stripe_customer_id
            )

            # Get payment method details
            card = payment_method.card

            # Check if we should make this the default
            make_default = False
            existing_methods = (
                self.supabase.table("payment_methods")
                .select("count(*)")
                .eq("organization_id", organization_id)
                .execute()
            )

            if existing_methods.count == 0:
                make_default = True

                # Update customer's default payment method
                stripe.Customer.modify(
                    stripe_customer_id,
                    invoice_settings={"default_payment_method": payment_method_id},
                )

            # Store in database
            payment_data = {
                "organization_id": organization_id,
                "stripe_payment_method_id": payment_method_id,
                "type": "card",
                "card_brand": card.brand,
                "last_four": card.last4,
                "expiry_month": card.exp_month,
                "expiry_year": card.exp_year,
                "is_default": make_default,
            }

            result = (
                self.supabase.table("payment_methods").insert(payment_data).execute()
            )

            return {
                "id": result.data[0]["id"],
                "type": card.brand.lower(),
                "lastFour": card.last4,
                "expiryDate": f"{card.exp_month}/{str(card.exp_year)[-2:]}",
                "isDefault": make_default,
            }

        except Exception as e:
            self.logger.error(f"Error adding payment method: {str(e)}")
            raise e

    def set_default_payment_method(
        self, organization_id: str, payment_method_id: str
    ) -> bool:
        """Set a payment method as default"""
        try:
            # Get payment method
            pm_result = (
                self.supabase.table("payment_methods")
                .select("stripe_payment_method_id")
                .eq("id", payment_method_id)
                .eq("organization_id", organization_id)
                .limit(1)
                .execute()
            )

            if not pm_result.data:
                raise Exception("Payment method not found")

            stripe_payment_method_id = pm_result.data[0]["stripe_payment_method_id"]

            # Get stripe customer ID
            sub_result = (
                self.supabase.table("subscriptions")
                .select("stripe_customer_id")
                .eq("organization_id", organization_id)
                .limit(1)
                .execute()
            )

            if not sub_result.data:
                raise Exception("No subscription found for this organization")

            stripe_customer_id = sub_result.data[0]["stripe_customer_id"]

            # Update customer's default payment method in Stripe
            stripe.Customer.modify(
                stripe_customer_id,
                invoice_settings={"default_payment_method": stripe_payment_method_id},
            )

            # Update database - first reset all to not default
            self.supabase.table("payment_methods").update({"is_default": False}).eq(
                "organization_id", organization_id
            ).execute()

            # Then set the selected one as default
            self.supabase.table("payment_methods").update({"is_default": True}).eq(
                "id", payment_method_id
            ).execute()

            return True

        except Exception as e:
            self.logger.error(f"Error setting default payment method: {str(e)}")
            return False

    def delete_payment_method(
        self, organization_id: str, payment_method_id: str
    ) -> bool:
        """Delete a payment method"""
        try:
            # Get payment method
            pm_result = (
                self.supabase.table("payment_methods")
                .select("stripe_payment_method_id, is_default")
                .eq("id", payment_method_id)
                .eq("organization_id", organization_id)
                .limit(1)
                .execute()
            )

            if not pm_result.data:
                raise Exception("Payment method not found")

            pm_data = pm_result.data[0]
            stripe_payment_method_id = pm_data["stripe_payment_method_id"]
            is_default = pm_data["is_default"]

            # If this is the default payment method, we need to set another one as default
            if is_default:
                # Find another payment method
                other_pm = (
                    self.supabase.table("payment_methods")
                    .select("id")
                    .eq("organization_id", organization_id)
                    .neq("id", payment_method_id)
                    .limit(1)
                    .execute()
                )

                if other_pm.data:
                    # Set the other payment method as default
                    self.set_default_payment_method(
                        organization_id, other_pm.data[0]["id"]
                    )

            # Detach the payment method from Stripe
            stripe.PaymentMethod.detach(stripe_payment_method_id)

            # Delete from database
            self.supabase.table("payment_methods").delete().eq(
                "id", payment_method_id
            ).execute()

            return True

        except Exception as e:
            self.logger.error(f"Error deleting payment method: {str(e)}")
            return False

    def cancel_subscription(self, organization_id: str) -> bool:
        """Cancel a subscription at period end"""
        try:
            # Get subscription
            sub_result = (
                self.supabase.table("subscriptions")
                .select("stripe_subscription_id")
                .eq("organization_id", organization_id)
                .limit(1)
                .execute()
            )

            if not sub_result.data:
                raise Exception("No subscription found for this organization")

            stripe_subscription_id = sub_result.data[0]["stripe_subscription_id"]

            # Cancel in Stripe
            stripe.Subscription.modify(
                stripe_subscription_id, cancel_at_period_end=True
            )

            # Update in database
            self.supabase.table("subscriptions").update(
                {"cancel_at_period_end": True}
            ).eq("stripe_subscription_id", stripe_subscription_id).execute()

            return True

        except Exception as e:
            self.logger.error(f"Error cancelling subscription: {str(e)}")
            return False

    def reactivate_subscription(self, organization_id: str) -> bool:
        """Reactivate a cancelled subscription"""
        try:
            # Get subscription
            sub_result = (
                self.supabase.table("subscriptions")
                .select("stripe_subscription_id")
                .eq("organization_id", organization_id)
                .limit(1)
                .execute()
            )

            if not sub_result.data:
                raise Exception("No subscription found for this organization")

            stripe_subscription_id = sub_result.data[0]["stripe_subscription_id"]

            # Reactivate in Stripe
            stripe.Subscription.modify(
                stripe_subscription_id, cancel_at_period_end=False
            )

            # Update in database
            self.supabase.table("subscriptions").update(
                {"cancel_at_period_end": False}
            ).eq("stripe_subscription_id", stripe_subscription_id).execute()

            return True

        except Exception as e:
            self.logger.error(f"Error reactivating subscription: {str(e)}")
            return False
