from datetime import datetime
from typing import Optional, Dict, Any
from app.models.base_model import BaseModel


class LeadSourceAlias(BaseModel):
    """Model representing a mapping from an alias source name to a canonical source."""

    def __init__(self) -> None:
        self.id: Optional[str] = None
        self.alias_name: Optional[str] = None
        self.canonical_source_id: Optional[str] = None
        self.user_id: Optional[str] = None
        self.created_at: Optional[datetime] = None
        # Joined field for display (not stored in DB)
        self.canonical_source_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "alias_name": self.alias_name,
            "canonical_source_id": self.canonical_source_id,
            "user_id": self.user_id,
        }

        if self.created_at:
            data["created_at"] = (
                self.created_at.isoformat()
                if isinstance(self.created_at, datetime)
                else self.created_at
            )

        # Include canonical_source_name if it's set (for API responses)
        if self.canonical_source_name:
            data["canonical_source_name"] = self.canonical_source_name

        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LeadSourceAlias":
        if not data:
            return None

        instance = cls()

        for key, value in data.items():
            if hasattr(instance, key):
                if key == "created_at" and value:
                    if isinstance(value, str):
                        try:
                            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
                        except ValueError:
                            pass
                setattr(instance, key, value)

        return instance
