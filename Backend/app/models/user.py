from typing import Optional
from datetime import datetime

from app.models.base_model import BaseModel


from typing import Optional, Dict, Any
from datetime import datetime

from app.models.base_model import BaseModel


class User(BaseModel):
    def __init__(self):
        self.id: str = None
        self.email: str = None
        self.email_notifications: Optional[bool] = None
        self.first_name: str = None
        self.last_name: str = None
        self.fub_account_id: Optional[str] = None
        self.full_name: str = None
        self.phone_number: Optional[str] = None
        self.role: str = None
        self.sms_notifications: Optional[bool] = None
        self.created_at: Optional[datetime] = None
        self.updated_at: Optional[datetime] = None
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert User object to dictionary for serialization"""
        data = vars(self).copy()
        
        # Handle datetime objects
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
                
        return data
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        """Create User object from dictionary"""
        user = cls()
        for key, value in data.items():
            if hasattr(user, key):
                if key in ["created_at", "updated_at"] and value:
                    try:
                        if isinstance(value, str):
                            setattr(
                                user, 
                                key,
                                datetime.fromisoformat(value.replace("Z", "+00:00"))
                            )
                        else:
                            setattr(user, key, value)
                    except (ValueError, TypeError):
                        setattr(user, key, value)
                else:
                    setattr(user, key, value)
        return user


class UserProfile(BaseModel):
    def __init__(self):
        self.id: str = None
        self.email: str = None
        self.full_name: Optional[str] = None
        self.phone_number: Optional[str] = None
        self.role: str = None
        self.fub_api_key: Optional[str] = None
        self.fub_import_tag: Optional[str] = None
        self.onboarding_completed: Optional[bool] = None
        self.email_notifications: Optional[bool] = None
        self.sms_notifications: Optional[bool] = None
        self.timezone: Optional[str] = None
        self.created_at: Optional[datetime] = None
        self.updated_at: Optional[datetime] = None
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert UserProfile object to dictionary for serialization"""
        data = vars(self).copy()
        
        # Handle datetime objects
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
                
        return data
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        """Create UserProfile object from dictionary"""
        profile = cls()
        for key, value in data.items():
            if hasattr(profile, key):
                if key in ["created_at", "updated_at"] and value:
                    try:
                        if isinstance(value, str):
                            setattr(
                                profile, 
                                key,
                                datetime.fromisoformat(value.replace("Z", "+00:00"))
                            )
                        else:
                            setattr(profile, key, value)
                    except (ValueError, TypeError):
                        setattr(profile, key, value)
                else:
                    setattr(profile, key, value)
        return profile