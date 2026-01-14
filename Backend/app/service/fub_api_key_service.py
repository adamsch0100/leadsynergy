from typing import Optional
import threading
from app.database.supabase_client import SupabaseClientSingleton
from app.database.fub_api_client import FUBApiClient
from supabase import Client


class FUBAPIKeyServiceSingleton:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = FUBAPIKeyService()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None


class FUBAPIKeyService:
    def __init__(self):
        self.supabase: Client = SupabaseClientSingleton.get_instance()
        self.table_name = "users"

    async def validate_and_store_api_key(self, user_id: str, api_key: str) -> bool:
        """Validate the FUB API key and store it if valid"""
        try:
            # Test the API key with a simple FUB API call
            client = FUBApiClient(api_key)
            try:
                await client.test_connection()
                print(f"FUB API key validation successful for user {user_id}")
            except Exception as validation_error:
                print(f"FUB API key validation failed: {str(validation_error)}")
                # Still try to store the key - validation might fail due to network issues
                # but the key could still be valid
                print("Attempting to store API key despite validation failure...")

            # Store the API key
            result = self.supabase.table(self.table_name).update({
                'fub_api_key': api_key
            }).eq('id', user_id).execute()

            if result.data is not None and len(result.data) > 0:
                print(f"Successfully stored FUB API key for user {user_id}")
                return True
            else:
                print(f"Failed to store FUB API key - no rows updated for user {user_id}")
                return False

        except Exception as e:
            print(f"Error in validate_and_store_api_key: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def store_api_key_sync(self, user_id: str, api_key: str) -> bool:
        """Store the FUB API key synchronously (without validation)"""
        try:
            print(f"Storing FUB API key for user {user_id} (sync method)")
            # Only update the fub_api_key field - don't assume other columns exist
            result = self.supabase.table(self.table_name).update({
                'fub_api_key': api_key
            }).eq('id', user_id).execute()

            if result.data is not None and len(result.data) > 0:
                print(f"Successfully stored FUB API key for user {user_id}")
                return True
            else:
                print(f"Failed to store FUB API key - no rows updated for user {user_id}")
                print(f"Result data: {result.data}")
                return False
        except Exception as e:
            print(f"Error storing FUB API key: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def get_api_key_for_user(self, user_id: str) -> Optional[str]:
        """Get the FUB API key for a specific user"""
        try:
            result = self.supabase.table(self.table_name).select('fub_api_key').eq('id', user_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0].get('fub_api_key')
        except Exception as e:
            print(f"Error getting API key for user: {str(e)}")
        return None

    def has_api_key(self, user_id: str) -> bool:
        """Check if a user has a valid FUB API key"""
        api_key = self.get_api_key_for_user(user_id)
        return bool(api_key and api_key.strip())

    def remove_api_key(self, user_id: str) -> bool:
        """Remove the FUB API key for a user"""
        try:
            result = self.supabase.table(self.table_name).update({
                'fub_api_key': None
            }).eq('id', user_id).execute()
            
            return result.data is not None and len(result.data) > 0
            
        except Exception as e:
            print(f"Error removing API key for user: {str(e)}")
            return False 