from supabase import create_client, Client
from dotenv import load_dotenv
import os
import threading

class SupabaseClientSingleton:
    _instance = None 
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls) -> Client:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    load_dotenv()
                    api_key = os.getenv('SUPABASE_SECRET_KEY')
                    supabase_url = os.getenv('SUPABASE_URL')
                    
                    if not api_key or not supabase_url:
                        raise ValueError("SUPABASE_SECRET_KEY and SUPABASE_URL must be set in environment variables")
                    
                    cls._instance = create_client(supabase_url, api_key)
        
        return cls._instance
    

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None


def main():
    try:
        # Get the Supabase client
        print("Attempting to connect to Supabase...")
        client = SupabaseClientSingleton.get_instance()

        # Perform a simple query to test connectivity
        # Using system tables - this should always exist
        result = client.table("leads").select('*').limit(1).execute()

        # If we get here without exceptions, connection is working
        print("Successfully connected to Supabase!")
        print(f"Connection URL: {os.getenv('SUPABASE_URL', 'Not found')}")
        print(f"Result: {result.data}")
        return True

    except Exception as e:
        print(f"Failed to connect to Supabase: {e}")
        return False

if __name__ == '__main__':
    main()