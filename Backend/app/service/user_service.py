from typing import List, Dict, Any, Optional
import threading
import uuid
from datetime import datetime

from app.models.user import User, UserProfile
from app.database.supabase_client import SupabaseClientSingleton
from supabase import Client


class UserServiceSingleton:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = UserService()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None


class UserService:
    def __init__(self):
        self.supabase: Client = SupabaseClientSingleton.get_instance()
        self.table_name = "users"
        self.profile_table_name = "user_profiles"

    def create(self, user: User) -> User:
        """Create a new user in the database"""
        if not user.id:
            user.id = str(uuid.uuid4())

        if not user.created_at:
            user.created_at = datetime.now()

        user.updated_at = datetime.now()

        # Set full_name if not already set
        if not user.full_name and (user.first_name or user.last_name):
            user.full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

        # Convert to dict for insertion
        data = user.to_dict()

        # Insert into Supabase
        result = self.supabase.table(self.table_name).insert(data).execute()

        # Update user with returned data
        if result.data and len(result.data) > 0:
            returned_data = result.data[0]
            for key, value in returned_data.items():
                setattr(user, key, value)

        return user

    def get_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID"""
        result = (
            self.supabase.table(self.table_name).select("*").eq("id", user_id).execute()
        )

        if result.data and len(result.data) > 0:
            return User.from_dict(result.data[0])
        return None

    def get_by_email(self, email: str) -> Optional[User]:
        """Get a user by email"""
        result = (
            self.supabase.table(self.table_name)
            .select("*")
            .eq("email", email)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return User.from_dict(result.data[0])
        return None

    def get_all(self) -> List[User]:
        """Get all users"""
        result = self.supabase.table(self.table_name).select("*").execute()

        users = []
        if result.data:
            for item in result.data:
                user = User.from_dict(item)
                users.append(user)

        return users

    def get_agents(self) -> List[User]:
        """Get all users with agent role"""
        result = (
            self.supabase.table(self.table_name)
            .select("*")
            .eq("role", "agent")
            .execute()
        )

        agents = []
        if result.data:
            for item in result.data:
                agent = User.from_dict(item)
                agents.append(agent)

        return agents

    def update(self, user: User) -> User:
        """Update a user"""
        if not user.id:
            raise ValueError("User must have an ID to be updated")

        user.updated_at = datetime.now()

        # Update full_name if first_name or last_name changed
        if user.first_name or user.last_name:
            user.full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()

        # Convert to dict for update
        data = user.to_dict()
        id_val = data.pop("id")  # Remove ID from the data to be updated

        # Update in Supabase
        result = (
            self.supabase.table(self.table_name).update(data).eq("id", id_val).execute()
        )

        # Update user with returned data
        if result.data and len(result.data) > 0:
            returned_data = result.data[0]
            for key, value in returned_data.items():
                setattr(user, key, value)

        return user

    def delete(self, user_id: str) -> bool:
        """Delete a user"""
        result = (
            self.supabase.table(self.table_name).delete().eq("id", user_id).execute()
        )
        return result.data is not None and len(result.data) > 0

    # User Profile methods
    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get a user profile by user ID"""
        result = (
            self.supabase.table(self.profile_table_name)
            .select("*")
            .eq("id", user_id)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return UserProfile.from_dict(result.data[0])
        return None

    def create_profile(self, profile: UserProfile) -> UserProfile:
        """Create a user profile"""
        if not profile.id:
            raise ValueError("Profile must have a user ID")

        if not profile.created_at:
            profile.created_at = datetime.now()

        profile.updated_at = datetime.now()

        # Convert to dict for insertion
        data = profile.to_dict()

        # Insert into Supabase
        result = self.supabase.table(self.profile_table_name).insert(data).execute()

        # Update profile with returned data
        if result.data and len(result.data) > 0:
            returned_data = result.data[0]
            for key, value in returned_data.items():
                setattr(profile, key, value)

        return profile

    def update_profile(self, profile: UserProfile) -> UserProfile:
        """Update a user profile"""
        if not profile.id:
            raise ValueError("Profile must have a user ID")

        profile.updated_at = datetime.now()

        # Convert to dict for update
        data = profile.to_dict()
        id_val = data.pop("id")  # Remove ID from the data to be updated

        # Update in Supabase
        result = (
            self.supabase.table(self.profile_table_name)
            .update(data)
            .eq("id", id_val)
            .execute()
        )

        # Update profile with returned data
        if result.data and len(result.data) > 0:
            returned_data = result.data[0]
            for key, value in returned_data.items():
                setattr(profile, key, value)

        return profile

    def update_notification_settings(
        self, user_id, email_notifications, sms_notifications
    ):
        try:
            # Check if both values are None
            if email_notifications is None and sms_notifications is None:
                return False

            # Update only the provided values
            update_data = {}
            if email_notifications is not None:
                update_data["email_notifications"] = email_notifications
            if sms_notifications is not None:
                update_data["sms_notifications"] = sms_notifications

            # Update timestamp
            update_data["updated_at"] = "now()"

            # Execute update
            result = (
                self.supabase.table("users")
                .update(update_data)
                .eq("id", user_id)
                .execute()
            )

            # Check result
            if result.data and len(result.data) > 0:
                return True
            return False
        except Exception as e:
            print(f"Error updating notification settings: {str(e)}")
            return False
