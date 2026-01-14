from typing import Optional, Dict, Any
from datetime import datetime

from app.models.base_model import BaseModel


class CreditTransaction(BaseModel):
    """
    Represents a credit transaction (usage, purchase, allocation, refund).
    Maps to the credit_transactions table.
    """

    # Transaction types
    TYPE_USAGE = 'usage'
    TYPE_PURCHASE = 'purchase'
    TYPE_SUBSCRIPTION = 'subscription'
    TYPE_SUBSCRIPTION_RENEWAL = 'subscription_renewal'
    TYPE_SUBSCRIPTION_UPDATE = 'subscription_update'
    TYPE_SUBSCRIPTION_CANCELED = 'subscription_canceled'
    TYPE_ALLOCATION = 'allocation'
    TYPE_REFUND = 'refund'

    # Status values
    STATUS_PENDING = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_REFUNDED = 'refunded'

    # Credit source values
    SOURCE_BROKER_PLAN = 'broker_plan'
    SOURCE_BROKER_BUNDLE = 'broker_bundle'
    SOURCE_BROKER_PERSONAL = 'broker_personal'
    SOURCE_BROKER_SHARED_PLAN = 'broker_shared_plan'
    SOURCE_BROKER_SHARED_BUNDLE = 'broker_shared_bundle'
    SOURCE_BROKER_SHARED_PERSONAL = 'broker_shared_personal'
    SOURCE_AGENT_BUNDLE = 'agent_bundle'
    SOURCE_AGENT_ALLOCATED = 'agent_allocated'

    def __init__(self):
        self.id: int = None
        self.user_id: str = None
        self.broker_id: Optional[str] = None  # If agent used broker's shared pool
        self.bundle_id: Optional[int] = None
        self.transaction_type: str = None
        self.enhancement_credits: int = 0
        self.criminal_credits: int = 0
        self.dnc_credits: int = 0
        self.amount: int = 0  # Amount in cents (for purchases)
        self.currency: str = 'USD'
        self.credit_source: Optional[str] = None
        self.description: Optional[str] = None
        self.status: str = 'completed'
        self.stripe_charge_id: Optional[str] = None
        self.stripe_session_id: Optional[str] = None
        self.created_at: Optional[datetime] = None

    @property
    def amount_dollars(self) -> float:
        """Get amount in dollars."""
        return self.amount / 100 if self.amount else 0

    @property
    def is_usage(self) -> bool:
        """Check if this is a usage transaction."""
        return self.transaction_type == self.TYPE_USAGE

    @property
    def is_purchase(self) -> bool:
        """Check if this is a purchase transaction."""
        return self.transaction_type == self.TYPE_PURCHASE

    @property
    def total_credits(self) -> int:
        """Get total credits in this transaction."""
        return (
            abs(self.enhancement_credits or 0) +
            abs(self.criminal_credits or 0) +
            abs(self.dnc_credits or 0)
        )

    def get_credit_summary(self) -> str:
        """Get a human-readable summary of credits."""
        parts = []
        if self.enhancement_credits:
            parts.append(f"{self.enhancement_credits} enhancement")
        if self.criminal_credits:
            parts.append(f"{self.criminal_credits} criminal")
        if self.dnc_credits:
            parts.append(f"{self.dnc_credits} DNC")
        return ", ".join(parts) if parts else "0 credits"

    def to_dict(self) -> Dict[str, Any]:
        """Convert CreditTransaction object to dictionary for serialization."""
        data = vars(self).copy()

        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CreditTransaction":
        """Create CreditTransaction object from dictionary."""
        transaction = cls()
        for key, value in data.items():
            if hasattr(transaction, key):
                if key == "created_at" and value:
                    try:
                        if isinstance(value, str):
                            setattr(
                                transaction,
                                key,
                                datetime.fromisoformat(value.replace("Z", "+00:00"))
                            )
                        else:
                            setattr(transaction, key, value)
                    except (ValueError, TypeError):
                        setattr(transaction, key, value)
                else:
                    setattr(transaction, key, value)
        return transaction
