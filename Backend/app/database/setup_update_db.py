# app/database/setup_db.py
import os
from dotenv import load_dotenv
import logging
from app.utils.constants import Credentials
from app.database.supabase_client import SupabaseClientSingleton

# Import the database setup class
from app.database.update_db import SupabaseDatabaseSetup

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db_setup")

# Load environment variables
load_dotenv()

def setup_database():
    """Set up the database schema if it doesn't exist"""
    try:
        # Get credentials
        creds = Credentials()
        
        # Check if direct URL is available
        direct_url = os.getenv("SUPABASE_POSTGRES_URL")
        
        if direct_url:
            # Use direct URL for database setup
            db_setup = SupabaseDatabaseSetup(direct_url)
            success = db_setup.create_database_schema()
            
            if success:
                logger.info("Database schema created or updated successfully")
            else:
                logger.error("Failed to create or update database schema")
            
            return success
        else:
            logger.error("SUPABASE_DIRECT_URL environment variable is not set")
            return False
            
    except Exception as e:
        logger.error(f"Error setting up database: {e}")
        return False
    

if __name__ == '__main__':
    setup_database()