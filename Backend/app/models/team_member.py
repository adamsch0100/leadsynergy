from typing import Optional, Dict, Any
import json
from datetime import datetime

from app.models.base_model import BaseModel


class TeamMember(BaseModel):
    """Model for team members with organization context"""

    def __init__(self):
        self.id: str = None
        self.user_id: str = None
        self.organization_id: str = None
        self.first_name: str = None
        self.last_name: str = None
        self.full_name: str = None
        self.email: str = None
        self.phone_number: Optional[str] = None
        self.role: str = "agent"
        self.email_notifications: bool = False
        self.sms_notifications: bool = False
        self.created_at: Optional[datetime] = None
        self.updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        data = vars(self).copy()

        # Handle datetime objects
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()

        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeamMember":
        team_member = cls()

        for key, value in data.items():
            if hasattr(team_member, key):
                setattr(team_member, key, value)

        return team_member

    @classmethod
    def from_user_and_org_data(
        cls, user_data: Dict[str, Any], org_user_data: Dict[str, Any]
    ) -> "TeamMember":
        """
        Create a TeamMember from separate user and organization_user data

        Args:
            user_data: Dictionary with user data
            org_user_data: Dictionary with organization_user data

        Returns:
            TeamMember object
        """
        team_member = cls()

        # Set user data
        team_member.id = user_data.get("id")
        team_member.user_id = user_data.get("id")
        team_member.first_name = user_data.get("first_name", "")
        team_member.last_name = user_data.get("last_name", "")
        team_member.full_name = user_data.get("full_name", "")
        team_member.email = user_data.get("email", "")
        team_member.phone_number = user_data.get("phone_number")
        team_member.email_notifications = user_data.get("email_notifications", False)
        team_member.sms_notifications = user_data.get("sms_notifications", False)
        team_member.created_at = user_data.get("created_at")
        team_member.updated_at = user_data.get("updated_at")

        # Set organization data
        team_member.organization_id = org_user_data.get("organization_id")
        team_member.role = org_user_data.get("role", "agent")

        return team_member
