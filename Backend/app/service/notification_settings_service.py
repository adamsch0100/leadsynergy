import json
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional

from app.database.supabase_client import SupabaseClientSingleton
from app.models.notification_settings import NotificationSettings


class NotificationSettingsServiceSingleton:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = NotificationSettingsService()

        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None


class NotificationSettingsService:
    def __init__(self) -> None:
        self.supabase = SupabaseClientSingleton.get_instance()
        self.table_name = "notification_settings"
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def get_by_organization(
        self, organization_id: str, user_id: Optional[str] = None
    ) -> Optional[NotificationSettings]:
        """
        Get notification settings for an organization or specific user

        Args:
            organization_id: The organization ID
            user_id: Optional user ID to get user-specific settings

        Returns:
            NotificationSettings object or None if not found
        """
        try:
            query = (
                self.supabase.table(self.table_name)
                .select("*")
                .eq("organization_id", organization_id)
            )

            if user_id:
                query = query.eq("user_id", user_id)
            else:
                query = query.is_("user_id", "null")

            result = query.execute()

            if result.data and len(result.data) > 0:
                settings = NotificationSettings.from_dict(result.data[0])
                return settings

            # If not found, create default settings
            return self.create_default_settings(organization_id, user_id)

        except Exception as e:
            self.logger.error(f"Error getting notification settings: {str(e)}")
            return None

    def create_default_settings(
        self, organization_id: str, user_id: Optional[str] = None
    ) -> NotificationSettings:
        """
        Create default notification settings for an organization or user

        Args:
            organization_id: The organization ID
            user_id: Optional user ID for user-specific settings

        Returns:
            Created NotificationSettings object
        """
        settings = NotificationSettings()
        settings.organization_id = organization_id
        settings.user_id = user_id
        settings.created_at = datetime.now()
        settings.updated_at = datetime.now()

        # Create settings in database
        try:
            data_dict = settings.to_dict()

            # Ensure settings is properly serialized as JSON
            if "settings" in data_dict and not isinstance(data_dict["settings"], str):
                data_dict["settings"] = json.dumps(data_dict["settings"])

            result = self.supabase.table(self.table_name).insert(data_dict).execute()

            if result.data and len(result.data) > 0:
                return NotificationSettings.from_dict(result.data[0])
            return settings

        except Exception as e:
            self.logger.error(f"Error creating default settings: {str(e)}")
            return settings

    def update(self, settings: NotificationSettings) -> Optional[NotificationSettings]:
        """
        Update notification settings

        Args:
            settings: The settings object to update

        Returns:
            Updated NotificationSettings object or None if failed
        """
        try:
            settings.updated_at = datetime.now()
            data_dict = settings.to_dict()

            # Ensure settings is properly serialized as JSON
            if "settings" in data_dict and not isinstance(data_dict["settings"], str):
                data_dict["settings"] = json.dumps(data_dict["settings"])

            result = (
                self.supabase.table(self.table_name)
                .update(data_dict)
                .eq("id", settings.id)
                .execute()
            )

            if result.data and len(result.data) > 0:
                return NotificationSettings.from_dict(result.data[0])
            return None

        except Exception as e:
            self.logger.error(f"Error updating notification settings: {str(e)}")
            return None
