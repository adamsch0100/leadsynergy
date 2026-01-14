from typing import Optional, Dict, Any
import json
from datetime import datetime

from app.models.base_model import BaseModel


class SystemSettings(BaseModel):
    """Model for system-wide settings"""

    def __init__(self):
        self.id: str = None
        self.fub_api_key: Optional[str] = None
        self.fub_api_key_set: bool = False
        self.webhook_url: Optional[str] = None
        self.min_update_interval_days: int = 5
        self.max_update_interval_days: int = 10
        self.fub_import_tag: str = "ReferralLink"
        self.created_at: Optional[datetime] = None
        self.updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        data = vars(self).copy()

        # Handle datetime objects
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()

        # Don't expose the actual API key when converting to dict
        if self.fub_api_key:
            data["fub_api_key"] = None

        return {k: v for k, v in data.items() if v is not None}

    def to_dict_with_api_key(self) -> Dict[str, Any]:
        """
        Convert to dictionary including the API key - use with caution
        """
        data = vars(self).copy()

        # Handle datetime objects
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()

        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemSettings":
        settings = cls()

        for key, value in data.items():
            if hasattr(settings, key):
                setattr(settings, key, value)

        return settings
