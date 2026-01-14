import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from app.models.base_model import BaseModel

class OrganizationUser(BaseModel):
    def __init__(self):
        self.id: str = None
        self.organization_id: str = None
        self.user_id: str = None
        self.role: str = None
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
    def from_dict(cls, data: Dict[str, Any]) -> "OrganizationUser":
        org_user = cls()
        for key, value in data.items():
            if hasattr(org_user, key):
                if key in ["created_at", "updated_at"] and value:
                    try:
                        if isinstance(value, str):
                            setattr(
                                org_user, 
                                key,
                                datetime.fromisoformat(value.replace("Z", "+00:00"))
                            )
                        else:
                            setattr(org_user, key, value)
                    except (ValueError, TypeError):
                        setattr(org_user, key, value)
                else:
                    setattr(org_user, key, value)
        return org_user