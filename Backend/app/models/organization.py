import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from app.models.base_model import BaseModel

class Organization(BaseModel):
    def __init__(self):
        self.id: str = None
        self.name: Optional[str] = None
        self.billing_email: Optional[str] = None
        self.settings: Optional[Dict[str, Any]] = None
        self.slug: str = None
        self.subsciption_end_date: datetime = None
        self.subscription_plan: str = None
        self.subscription_status: str = None
        self.created_at: datetime = None
        self.updated_at: Optional[datetime] = None
        
    def to_dict(self) -> Dict[str, Any]:
        data = vars(self).copy()
        
        # Handle datetime objects
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
                
        return data
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Organization":
        org = cls()
        for key, value in data.items():
            if hasattr(org, key):
                if key in ["created_at", "updated_at", "subsciption_end_date"] and value:
                    try:
                        if isinstance(value, str):
                            setattr(
                                org, 
                                key,
                                datetime.fromisoformat(value.replace("Z", "+00:00"))
                            )
                        else:
                            setattr(org, key, value)
                    except (ValueError, TypeError):
                        setattr(org, key, value)
                else:
                    setattr(org, key, value)
        return org