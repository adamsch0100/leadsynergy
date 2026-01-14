from typing import Optional, Dict, Any
from datetime import datetime

from app.models.base_model import BaseModel


class CreditBundle(BaseModel):
    """
    Represents a purchasable credit package (subscription or add-on).
    Maps to the credit_bundles table.
    """

    def __init__(self):
        self.id: int = None
        self.name: str = None
        self.description: Optional[str] = None
        self.price: int = 0  # Price in cents
        self.enhancement_credits: int = 0
        self.criminal_credits: int = 0
        self.dnc_credits: int = 0
        self.stripe_price_id: Optional[str] = None
        self.bundle_type: str = 'addon'  # 'addon' or 'subscription'
        self.is_active: bool = True
        self.is_test: bool = False
        self.created_at: Optional[datetime] = None
        self.updated_at: Optional[datetime] = None

    @property
    def price_dollars(self) -> float:
        """Get price in dollars."""
        return self.price / 100 if self.price else 0

    @property
    def is_subscription(self) -> bool:
        """Check if this is a subscription plan."""
        return self.bundle_type == 'subscription'

    @property
    def is_addon(self) -> bool:
        """Check if this is an add-on bundle."""
        return self.bundle_type == 'addon'

    @property
    def total_credits(self) -> int:
        """Get total credits in this bundle."""
        return (
            (self.enhancement_credits or 0) +
            (self.criminal_credits or 0) +
            (self.dnc_credits or 0)
        )

    def get_features_list(self) -> list:
        """Get a list of features for display."""
        features = []
        if self.enhancement_credits > 0:
            features.append(f"{self.enhancement_credits} enhancement credits")
        if self.criminal_credits > 0:
            features.append(f"{self.criminal_credits} criminal search credits")
        if self.dnc_credits > 0:
            features.append(f"{self.dnc_credits} DNC check credits")
        return features

    def to_dict(self) -> Dict[str, Any]:
        """Convert CreditBundle object to dictionary for serialization."""
        data = vars(self).copy()

        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CreditBundle":
        """Create CreditBundle object from dictionary."""
        bundle = cls()
        for key, value in data.items():
            if hasattr(bundle, key):
                if key in ["created_at", "updated_at"] and value:
                    try:
                        if isinstance(value, str):
                            setattr(
                                bundle,
                                key,
                                datetime.fromisoformat(value.replace("Z", "+00:00"))
                            )
                        else:
                            setattr(bundle, key, value)
                    except (ValueError, TypeError):
                        setattr(bundle, key, value)
                else:
                    setattr(bundle, key, value)
        return bundle
