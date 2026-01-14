import json
from datetime import datetime
from typing import Dict, Any, Optional

from app.models.base_model import BaseModel


class NotificationSettings(BaseModel):
    def __init__(self) -> None:
        self.id: str = None
        self.organization_id: str = None
        self.user_id: str = None  # If null, applies to the entire organization
        self.settings: Dict[str, Dict[str, bool]] = {
            "new-lead": {"email": True, "sms": True, "push": False, "slack": False},
            "stage-update": {
                "email": True,
                "sms": False,
                "push": False,
                "slack": False,
            },
            "commission": {"email": True, "sms": False, "push": False, "slack": False},
        }
        self.created_at: datetime = None
        self.updated_at: datetime = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the model to a dictionary"""
        data = {
            "id": self.id,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "settings": self.settings,
        }

        if self.created_at:
            data["created_at"] = (
                self.created_at.isoformat()
                if isinstance(self.created_at, datetime)
                else self.created_at
            )

        if self.updated_at:
            data["updated_at"] = (
                self.updated_at.isoformat()
                if isinstance(self.updated_at, datetime)
                else self.updated_at
            )

        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotificationSettings":
        """Create model instance from dictionary"""
        instance = cls()

        for key, value in data.items():
            if hasattr(instance, key):
                if key in ["created_at", "updated_at"] and value:
                    if isinstance(value, str):
                        try:
                            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
                        except ValueError:
                            pass
                if key == "settings" and isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        pass

                setattr(instance, key, value)

        return instance
