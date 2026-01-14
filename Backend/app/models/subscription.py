import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from app.models.base_model import BaseModel


class SubscriptionPlan(BaseModel):
    def __init__(self):
        self.id: str = None
        self.name: str = None
        self.stripe_price_id: str = None
        self.amount: float = None
        self.currency: str = None
        self.interval: str = None  # 'month', 'year'
        self.features: Dict[str, Any] = None
        self.limits: Dict[str, Any] = None
        self.created_at: datetime = None
        self.updated_at: Optional[datetime] = None


class Subscription(BaseModel):
    def __init__(self):
        self.id: str = None
        self.organization_id: str = None
        self.stripe_customer_id: str = None
        self.stripe_subscription_id: str = None
        self.plan_id: Optional[str] = None
        self.status: str = (
            None  # 'active', 'trialing', 'past_due', 'canceled', 'incomplete'
        )
        self.current_period_start: datetime = None
        self.current_period_end: datetime = None
        self.cancel_at_period_end: bool = False
        self.trial_end: Optional[datetime] = None
        self.created_at: datetime = None
        self.updated_at: Optional[datetime] = None
        self.subscription_plan: Optional[SubscriptionPlan] = None
        self.usage: Optional[Dict[str, Dict[str, int]]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subscription":
        subscription = super().from_dict(data)

        # Handle nested subscription plan if present
        if "subscription_plans" in data and data["subscription_plans"]:
            subscription.subscription_plan = SubscriptionPlan.from_dict(
                data["subscription_plans"]
            )

        return subscription

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()

        # Handle nested subscription plan
        if self.subscription_plan:
            data["subscription_plan"] = self.subscription_plan.to_dict()

        return data

    def format_subscription_data(self) -> Dict[str, Any]:
        """Format subscription data for API response"""
        plan_name = (
            self.subscription_plan.name.lower() if self.subscription_plan else "free"
        )

        return {
            "id": self.id,
            "plan": plan_name,
            "organizationId": self.organization_id,
            "status": self.status,
            "trialEndsAt": self.format_datetime(self.trial_end),
            "currentPeriodEnd": self.format_datetime(self.current_period_end),
            "cancelAtPeriodEnd": self.cancel_at_period_end,
            "usage": self.usage
            or {
                "teamMembers": {"current": 0, "limit": 1},
                "leadSources": {"current": 0, "limit": 1},
                "storage": {"current": 0, "limit": 1},
            },
        }

    @staticmethod
    def get_default_subscription(organization_id: str) -> Dict[str, Any]:
        """Return default free subscription data"""
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

    def cancel(self) -> bool:
        """Mark subscription as cancelled at period end"""
        self.cancel_at_period_end = True
        return True

    def reactivate(self) -> bool:
        """Reactivate a cancelled subscription"""
        self.cancel_at_period_end = False
        return True


class PaymentMethod(BaseModel):
    def __init__(self):
        self.id: str = None
        self.organization_id: str = None
        self.stripe_payment_method_id: str = None
        self.type: str = None  # 'card', 'bank_account', etc.
        self.card_brand: Optional[str] = None  # 'visa', 'mastercard', 'amex', etc.
        self.last_four: Optional[str] = None
        self.expiry_month: Optional[int] = None
        self.expiry_year: Optional[int] = None
        self.is_default: bool = False
        self.created_at: datetime = None
        self.updated_at: Optional[datetime] = None

    def format_payment_method(self) -> Dict[str, Any]:
        """Format payment method data for API response"""
        return {
            "id": self.id,
            "type": self.card_brand.lower() if self.card_brand else self.type,
            "lastFour": self.last_four,
            "expiryDate": (
                f"{self.expiry_month}/{str(self.expiry_year)[-2:]}"
                if self.expiry_month and self.expiry_year
                else None
            ),
            "isDefault": self.is_default,
        }

    def set_as_default(self) -> None:
        """Set this payment method as the default"""
        self.is_default = True

    @classmethod
    def from_stripe_payment_method(
        cls, stripe_pm: Dict[str, Any], organization_id: str, is_default: bool = False
    ) -> "PaymentMethod":
        """Create a PaymentMethod instance from Stripe payment method data"""
        pm = cls()
        pm.organization_id = organization_id
        pm.stripe_payment_method_id = stripe_pm.id
        pm.type = stripe_pm.type

        if hasattr(stripe_pm, "card") and stripe_pm.card:
            pm.card_brand = stripe_pm.card.brand
            pm.last_four = stripe_pm.card.last4
            pm.expiry_month = stripe_pm.card.exp_month
            pm.expiry_year = stripe_pm.card.exp_year

        pm.is_default = is_default
        pm.created_at = datetime.now()

        return pm


class Invoice(BaseModel):
    def __init__(self):
        self.id: str = None
        self.organization_id: str = None
        self.stripe_invoice_id: str = None
        self.stripe_payment_intent_id: Optional[str] = None
        self.amount_due: float = None
        self.amount_paid: float = None
        self.currency: str = None
        self.status: str = None  # 'paid', 'open', 'uncollectible', 'void'
        self.description: Optional[str] = None
        self.invoice_pdf: Optional[str] = None
        self.invoice_date: datetime = None
        self.created_at: datetime = None
        self.updated_at: Optional[datetime] = None

    def format_invoice(self) -> Dict[str, Any]:
        """Format invoice data for API response"""
        return {
            "id": self.id,
            "date": self.format_datetime(self.invoice_date),
            "description": self.description,
            "amount": f"${self.amount_paid}",
            "status": self.status,
            "invoiceUrl": self.invoice_pdf,
        }

    @classmethod
    def from_stripe_invoice(
        cls, stripe_invoice: Dict[str, Any], organization_id: str
    ) -> "Invoice":
        """Create an Invoice instance from Stripe invoice data"""
        invoice = cls()
        invoice.organization_id = organization_id
        invoice.stripe_invoice_id = stripe_invoice.id
        invoice.stripe_payment_intent_id = stripe_invoice.payment_intent
        invoice.amount_due = stripe_invoice.amount_due / 100  # Convert from cents
        invoice.amount_paid = stripe_invoice.amount_paid / 100  # Convert from cents
        invoice.currency = stripe_invoice.currency
        invoice.status = stripe_invoice.status
        invoice.description = (
            stripe_invoice.description or f"Invoice {stripe_invoice.number}"
        )
        invoice.invoice_pdf = stripe_invoice.invoice_pdf
        invoice.invoice_date = datetime.fromtimestamp(stripe_invoice.created)
        invoice.created_at = datetime.now()

        return invoice


class SubscriptionUsage(BaseModel):
    def __init__(self):
        self.id: str = None
        self.organization_id: str = None
        self.subscription_id: Optional[str] = None
        self.metric_name: str = None  # 'team_members', 'lead_sources', 'storage'
        self.current_value: int = 0
        self.limit_value: int = 0
        self.created_at: datetime = None
        self.updated_at: Optional[datetime] = None

    def is_within_limit(self) -> bool:
        """Check if current usage is within the allowed limit"""
        return self.current_value <= self.limit_value

    def percentage_used(self) -> float:
        """Calculate percentage of limit used"""
        if self.limit_value == 0:
            return 100.0  # Avoid division by zero
        return (self.current_value / self.limit_value) * 100

    def increment_usage(self, amount: int = 1) -> None:
        """Increment usage by the specified amount"""
        self.current_value += amount
        self.updated_at = datetime.now()

    def decrement_usage(self, amount: int = 1) -> None:
        """Decrement usage by the specified amount"""
        self.current_value = max(0, self.current_value - amount)
        self.updated_at = datetime.now()

    def update_limit(self, new_limit: int) -> None:
        """Update the limit value"""
        self.limit_value = new_limit
        self.updated_at = datetime.now()
