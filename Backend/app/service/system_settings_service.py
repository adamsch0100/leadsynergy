import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from supabase import Client

from app.database.supabase_client import SupabaseClientSingleton
from app.models.system_settings import SystemSettings


class SystemSettingsService:
    def __init__(self) -> None:
        self.supabase: Client = SupabaseClientSingleton.get_instance()
        self.table_name = "system_settings"

    def get(self) -> SystemSettings:
        """
        Get the system settings. If none exist, create default settings.

        Returns:
            SystemSettings object
        """
        try:
            # Get the first system settings record (there should only be one)
            result = self.supabase.table(self.table_name).select("*").limit(1).execute()

            if not result.data:
                # If no settings exist, create default ones
                return self.create_default()

            # Debug: Print what columns the database actually has
            print(f"[SystemSettings] Raw DB data: {result.data[0]}")
            print(f"[SystemSettings] DB columns: {list(result.data[0].keys())}")

            # Convert to SystemSettings object
            return SystemSettings.from_dict(result.data[0])
        except Exception as e:
            print(f"Error getting system settings: {str(e)}")
            # Return default settings if there was an error
            return SystemSettings()

    def create_default(self) -> SystemSettings:
        """
        Create default system settings

        Returns:
            SystemSettings object
        """
        try:
            # Create default settings
            settings = SystemSettings()
            settings.id = str(uuid.uuid4())
            now = datetime.now()
            settings.created_at = now
            settings.updated_at = now

            # Insert into database - use dict with serialized datetimes
            data = settings.to_dict_with_api_key()
            # Ensure datetime fields are serialized
            if 'created_at' in data and isinstance(data['created_at'], datetime):
                data['created_at'] = data['created_at'].isoformat()
            if 'updated_at' in data and isinstance(data['updated_at'], datetime):
                data['updated_at'] = data['updated_at'].isoformat()
            result = self.supabase.table(self.table_name).insert(data).execute()

            if result.data and len(result.data) > 0:
                return SystemSettings.from_dict(result.data[0])

            return settings
        except Exception as e:
            print(f"Error creating default system settings: {str(e)}")
            return SystemSettings()

    def update(self, data: Dict[str, Any]) -> Optional[SystemSettings]:
        """
        Update system settings

        Args:
            data: Dictionary with data to update

        Returns:
            Updated SystemSettings object or None if update failed
        """
        try:
            print(f"[SystemSettings] Updating with data: {data}")

            # Get current settings
            settings = self.get()
            print(f"[SystemSettings] Current settings id: {settings.id}")

            if not settings.id:
                print("[SystemSettings] No settings ID found!")
                return None

            # Update settings with new data
            for key, value in data.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
                    print(f"[SystemSettings] Set {key} = {value}")
                else:
                    print(f"[SystemSettings] Warning: attribute {key} not found on settings")

            settings.updated_at = datetime.now()

            # Update in database
            update_data = {k: v for k, v in data.items()}
            update_data["updated_at"] = settings.updated_at.isoformat()

            print(f"[SystemSettings] Sending to DB: {update_data}")

            result = (
                self.supabase.table(self.table_name)
                .update(update_data)
                .eq("id", settings.id)
                .execute()
            )

            print(f"[SystemSettings] DB result: {result.data}")

            if result.data and len(result.data) > 0:
                return SystemSettings.from_dict(result.data[0])

            return None
        except Exception as e:
            print(f"Error updating system settings: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def update_api_key(self, api_key: str) -> bool:
        """
        Update the FUB API key

        Args:
            api_key: The new API key

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current settings
            settings = self.get()

            if not settings.id:
                return False

            # Update API key
            update_data = {
                "fub_api_key": api_key,
                "fub_api_key_set": True,
                "updated_at": datetime.now().isoformat(),
            }

            result = (
                self.supabase.table(self.table_name)
                .update(update_data)
                .eq("id", settings.id)
                .execute()
            )

            return result.data and len(result.data) > 0
        except Exception as e:
            print(f"Error updating API key: {str(e)}")
            return False


class SystemSettingsServiceSingleton:
    _instance = None

    @classmethod
    def get_instance(cls) -> SystemSettingsService:
        if cls._instance is None:
            cls._instance = SystemSettingsService()
        return cls._instance
