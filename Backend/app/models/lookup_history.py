from typing import Optional, Dict, Any
from datetime import datetime

from app.models.base_model import BaseModel


class LookupHistory(BaseModel):
    """
    Represents a record of an enrichment search/lookup.
    Maps to the lookup_history table.
    """

    # Search types
    TYPE_CONTACT_ENRICHMENT = 'contact_enrichment'
    TYPE_REVERSE_PHONE = 'reverse_phone'
    TYPE_REVERSE_EMAIL = 'reverse_email'
    TYPE_OWNER_SEARCH = 'owner_search'
    TYPE_CRIMINAL_SEARCH = 'criminal_search'
    TYPE_SAFETY_CHECK = 'safety_check'
    TYPE_DNC_CHECK = 'dnc'
    TYPE_ADVANCED_PERSON = 'advanced_person_search'

    # Usage types (which credit pool was used)
    USAGE_ENHANCEMENT = 'enhancement'
    USAGE_CRIMINAL = 'criminal'
    USAGE_DNC = 'dnc'

    def __init__(self):
        self.id: str = None
        self.user_id: str = None
        self.search_type: str = None
        self.criteria: Optional[Dict[str, Any]] = None
        self.result: Optional[Dict[str, Any]] = None
        self.success: bool = False
        self.message: Optional[str] = None
        self.usage_type: Optional[str] = None  # Which credit type was used
        self.lead_id: Optional[str] = None
        self.fub_person_id: Optional[str] = None
        self.billing_period_start: Optional[datetime] = None
        self.billing_period_end: Optional[datetime] = None
        self.created_at: Optional[datetime] = None

    @property
    def search_type_display(self) -> str:
        """Get human-readable search type."""
        type_map = {
            'contact_enrichment': 'Contact Enrichment',
            'reverse_phone': 'Reverse Phone Lookup',
            'reverse_email': 'Reverse Email Lookup',
            'owner_search': 'Property Owner Search',
            'criminal_search': 'Criminal History Search',
            'safety_check': 'Safety Check',
            'dnc': 'DNC Check',
            'advanced_person_search': 'Advanced Person Search'
        }
        return type_map.get(self.search_type, self.search_type or 'Unknown')

    @property
    def status_display(self) -> str:
        """Get human-readable status."""
        return 'Success' if self.success else 'Failed'

    @property
    def criteria_summary(self) -> str:
        """Get a brief summary of search criteria."""
        if not self.criteria:
            return 'N/A'

        parts = []

        # Try common field names
        if self.criteria.get('firstName') or self.criteria.get('lastName'):
            name = f"{self.criteria.get('firstName', '')} {self.criteria.get('lastName', '')}".strip()
            if name:
                parts.append(name)

        if self.criteria.get('phone') or self.criteria.get('Phone'):
            phone = self.criteria.get('phone') or self.criteria.get('Phone')
            parts.append(f"Phone: {phone}")

        if self.criteria.get('email') or self.criteria.get('Email'):
            email = self.criteria.get('email') or self.criteria.get('Email')
            parts.append(f"Email: {email}")

        if self.criteria.get('address') or self.criteria.get('AddressLine1'):
            address = self.criteria.get('address') or self.criteria.get('AddressLine1')
            parts.append(f"Address: {address}")

        return '; '.join(parts) if parts else str(self.criteria)[:50]

    @classmethod
    def get_usage_type_for_search(cls, search_type: str) -> str:
        """Get the credit usage type for a given search type."""
        if search_type in [cls.TYPE_CRIMINAL_SEARCH, cls.TYPE_SAFETY_CHECK]:
            return cls.USAGE_CRIMINAL
        elif search_type == cls.TYPE_DNC_CHECK:
            return cls.USAGE_DNC
        else:
            return cls.USAGE_ENHANCEMENT

    def to_dict(self) -> Dict[str, Any]:
        """Convert LookupHistory object to dictionary for serialization."""
        data = vars(self).copy()

        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LookupHistory":
        """Create LookupHistory object from dictionary."""
        history = cls()
        datetime_fields = ["created_at", "billing_period_start", "billing_period_end"]

        for key, value in data.items():
            if hasattr(history, key):
                if key in datetime_fields and value:
                    try:
                        if isinstance(value, str):
                            setattr(
                                history,
                                key,
                                datetime.fromisoformat(value.replace("Z", "+00:00"))
                            )
                        else:
                            setattr(history, key, value)
                    except (ValueError, TypeError):
                        setattr(history, key, value)
                else:
                    setattr(history, key, value)
        return history
