from dotenv import load_dotenv
import os

load_dotenv()
class Credentials:
    def __init__(self) -> None:
        # Credentials (support both naming conventions)
        self.FUB_API_KEY = os.getenv('FUB_API_KEY') or os.getenv('FOLLOWUPBOSS_API_KEY')
        self.SUPABASE_URL = os.getenv('SUPABASE_URL')
        self.SUPABASE_KEY = os.getenv('SUPABASE_KEY')
        self.SUPABASE_SECRET_KEY = os.getenv('SUPABASE_SECRET_KEY') or os.getenv('SUPABASE_JWT_SECRET')
        self.SUPABASE_POSTGRES_URL = os.getenv('SUPABASE_POSTGRES_URL')
        # Domains
        self.NGROK_DOMAIN = os.getenv('NGROK_DOMAIN')
        # Event Names
        self.TAG_EVENT_NAME = os.getenv('TAG_EVENT_NAME')
        self.STAGE_EVENT_NAME = os.getenv('STAGE_EVENT_NAME')
        self.NOTE_CREATED_EVENT_NAME = os.getenv('NOTE_CREATED_EVENT_NAME')
        self.NOTE_UPDATED_EVENT_NAME = os.getenv('NOTE_UPDATED_EVENT_NAME')
        # System Names
        self.TAG_SYSTEM_NAME = os.getenv('TAG_SYSTEM_NAME')
        self.STAGE_SYSTEM_NAME = os.getenv('STAGE_SYSTEM_NAME')
        self.NOTE_CREATED_SYSTEM_NAME = os.getenv('NOTE_CREATED_SYSTEM_NAME')
        # System Keys
        self.TAG_SYSTEM_KEY = os.getenv('TAG_SYSTEM_KEY')
        self.STAGE_SYSTEM_KEY = os.getenv('STAGE_SYSTEM_KEY')
        self.NOTE_SYSTEM_KEY = os.getenv('NOTE_SYSTEM_KEY')        
        # External Source Credentials
        self.REDFIN_EMAIL = os.getenv('REDFIN_EMAIL')
        self.REDFIN_PASSWORD = os.getenv('REDFIN_PASSWORD')
        self.HOMELIGHT_EMAIL = os.getenv('HOMELIGHT_EMAIL')
        self.HOMELIGHT_PASSWORD = os.getenv('HOMELIGHT_PASSWORD')
        self.REFERRAL_EXCHANGE_EMAIL = os.getenv('REFERRAL_EXCHANGE_EMAIL')
        self.REFERRAL_EXCHANGE_PASSWORD = os.getenv('REFERRAL_EXCHANGE_PASSWORD')
        self.MY_AGENT_FINDER_EMAIL = os.getenv('MY_AGENT_FINDER_EMAIL')
        self.MY_AGENT_FINDER_PASSWORD = os.getenv('MY_AGENT_FINDER_PASSWORD')
        self.AGENT_PRONTO_EMAIL = os.getenv('AGENT_PRONTO_EMAIL')
        self.AGENT_PRONTO_PASSWORD = os.getenv('AGENT_PRONTO_PASSWORD')

        # Gmail credentials for 2FA code retrieval
        self.GMAIL_EMAIL = os.getenv('GMAIL_EMAIL')
        self.GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD')

        # AI Agent System credentials for FUB API identification
        self.AI_AGENT_SYSTEM_NAME = os.getenv('AI_AGENT_SYSTEM_NAME', 'leadsynergy-ai')
        self.AI_AGENT_SYSTEM_KEY = os.getenv('AI_AGENT_SYSTEM_KEY')

        # FUB Web Login Credentials (for Playwright browser automation)
        self.FUB_LOGIN_EMAIL = os.getenv('FUB_LOGIN_EMAIL')
        self.FUB_LOGIN_PASSWORD = os.getenv('FUB_LOGIN_PASSWORD')
        self.FUB_LOGIN_TYPE = os.getenv('FUB_LOGIN_TYPE', 'email')  # email, google, microsoft

        # Validate critical credentials
        self._validate_required_credentials()

    def get(self, key: str, default=None):
        """Get credential value with optional default (dict-like access)."""
        return getattr(self, key, default) 
        
    def _validate_required_credentials(self):
        """Validate that critical credentials are present."""
        required_credentials = [
            'FUB_API_KEY', 'SUPABASE_URL', 'SUPABASE_KEY', 
            'SUPABASE_SECRET_KEY'
        ]
        
        missing = [cred for cred in required_credentials 
                  if getattr(self, cred) is None]
        
        if missing:
            raise EnvironmentError(
                f"Missing required environment variables: {', '.join(missing)}"
            )
        
        # SUPABASE_POSTGRES_URL is optional - only needed for migrations
        if not self.SUPABASE_POSTGRES_URL:
            import warnings
            warnings.warn(
                "SUPABASE_POSTGRES_URL not set. Database migrations will not work. "
                "Get it from Supabase Dashboard -> Settings -> Database -> Connection string (Direct connection)"
            )