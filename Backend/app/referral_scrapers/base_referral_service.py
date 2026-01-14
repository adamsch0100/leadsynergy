from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
import logging
from dotenv import load_dotenv
import os

from app.models.lead import Lead
from app.referral_scrapers.utils.driver_service import DriverService
from app.referral_scrapers.utils.web_interaction_simulator import WebInteractionSimulator
from app.utils.constants import Credentials

load_dotenv()

class BaseReferralService(ABC):
    """Base class for all referral platform services
    Provides common interface and functionality for different platforms
    """
    
    def __init__(self, lead: Lead, organization_id: str = None) -> None:
        self.lead = lead
        self.organization_id = organization_id
        self.is_logged_in = False
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        
        # Setup logging
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
            
        # Check if proxy usage is enabled via environment variable
        self.use_proxy = os.getenv("USE_PROXY", "false").lower() in ["true", "1", "yes"]
        
        # Initialize services with organization-specific proxy support
        self.driver_service = DriverService(organization_id=self.organization_id)
        self.wis = WebInteractionSimulator()
        
        # Get Credentials
        self._setup_credentials()
        
        # Initialize proxy service for HTTP requests
        self._setup_proxy_service()
        

    def _setup_credentials(self):
        """Setup credentials from database (lead_source_settings.metadata) with fallback to environment variables"""
        
        try:
            # First, try to get credentials from database (lead_source_settings.metadata)
            platform_name = self.get_platform_name()
            from app.service.lead_source_settings_service import LeadSourceSettingsSingleton
            
            settings_service = LeadSourceSettingsSingleton.get_instance()
            lead_source_settings = settings_service.get_by_source_name(platform_name)
            
            if lead_source_settings and lead_source_settings.metadata:
                credentials = lead_source_settings.metadata.get('credentials', {})
                if credentials:
                    self.email = credentials.get('email')
                    self.password = credentials.get('password')
                    
                    if self.email and self.password:
                        self.logger.info(f"Loaded credentials for {platform_name} from database")
                        return
            
            # Fallback to environment variables if not found in database
            self.logger.info(f"Credentials not found in database for {platform_name}, trying environment variables")
            self.email = os.getenv(f"{platform_name.upper()}_EMAIL")
            self.password = os.getenv(f"{platform_name.upper()}_PASSWORD")
            
            if not self.email or not self.password:
                self.logger.warning(f"Missing credentials for {platform_name} (not in database or environment)")
        except Exception as e:
            self.logger.error(f"Error setting up credentials: {e}")
            # Fallback to environment variables on error
            try:
                platform_name = self.get_platform_name()
                self.email = os.getenv(f"{platform_name.upper()}_EMAIL")
                self.password = os.getenv(f"{platform_name.upper()}_PASSWORD")
            except:
                pass

    def _setup_proxy_service(self):
        """Setup proxy service for HTTP requests"""
        try:
            from app.service.proxy_service import ProxyServiceSingleton
            
            if self.organization_id and self.use_proxy:
                self.proxy_service = ProxyServiceSingleton.get_instance()
                self.proxy_dict = self.proxy_service.get_proxy_dict_for_requests(self.organization_id)
                
                if self.proxy_dict:
                    self.logger.info(f"HTTP proxy configured for organization {self.organization_id}")
                else:
                    self.logger.warning(f"No HTTP proxy configuration found for organization {self.organization_id}")
                    self.proxy_dict = None
            else:
                self.proxy_service = None
                self.proxy_dict = None
                if not self.use_proxy:
                    self.logger.info("HTTP proxy usage is disabled via USE_PROXY environment variable")
                else:
                    self.logger.info("No organization ID provided, running HTTP requests without proxy")
                
        except Exception as e:
            self.logger.error(f"Error setting up proxy service: {e}")
            self.proxy_service = None
            self.proxy_dict = None

    def make_http_request(self, url: str, method: str = "GET", **kwargs) -> Any:
        """
        Make HTTP request with organization-specific proxy support
        
        Args:
            url: The URL to request
            method: HTTP method (GET, POST, etc.)
            **kwargs: Additional arguments for requests
            
        Returns:
            Response object or None if failed
        """
        try:
            import requests
            
            # Add proxy configuration if available and enabled
            if self.use_proxy and self.proxy_dict:
                kwargs['proxies'] = self.proxy_dict
                self.logger.debug(f"Making {method} request to {url} via proxy")
            else:
                self.logger.debug(f"Making {method} request to {url} without proxy")
            
            # Add default timeout if not specified
            if 'timeout' not in kwargs:
                kwargs['timeout'] = 30
                
            # Make the request
            if method.upper() == "GET":
                response = requests.get(url, **kwargs)
            elif method.upper() == "POST":
                response = requests.post(url, **kwargs)
            elif method.upper() == "PUT":
                response = requests.put(url, **kwargs)
            elif method.upper() == "DELETE":
                response = requests.delete(url, **kwargs)
            else:
                response = requests.request(method, url, **kwargs)
                
            return response
            
        except Exception as e:
            self.logger.error(f"Error making HTTP request to {url}: {str(e)}")
            return None
            
    
    @abstractmethod
    def login(self) -> bool:
        """Log in to the platform. Must be implemented by subclasses"""
        pass
    
    
    @abstractmethod
    def update_customers(self, status_to_select: Any) -> bool:
        """Update all customers with the given status"""
        pass
    
    
    @classmethod
    @abstractmethod
    def get_platform_name(cls) -> str:
        """Return the name of the platform this service handles"""
        pass
    
    
    @staticmethod
    def calculate_next_run_time(min_delay_hours: int = 72, max_delay_hours: int = 220) -> datetime:
        """Calculate next time the service should run"""
        # Default implementation - can be overridden by subclasses
        import random
        from datetime import datetime, timedelta
        
        delay_hours = random.randint(min_delay_hours, max_delay_hours)
        return datetime.now() + timedelta(hours=delay_hours)
            