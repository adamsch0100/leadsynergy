import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from supabase import Client

from app.database.supabase_client import SupabaseClientSingleton


class ProxyService:
    """
    Service for managing organization-specific IPRoyal proxies for referral scraping
    """
    
    def __init__(self) -> None:
        self.supabase: Client = SupabaseClientSingleton.get_instance()
        self.logger = logging.getLogger(__name__)
        
        # Setup logging
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
            
        # IPRoyal configuration from environment
        self.iproyal_base_host = os.getenv("IPROYAL_HOST", "geo.iproyal.com")
        self.iproyal_http_port = os.getenv("IPROYAL_HTTP_PORT", "12321")
        self.iproyal_socks5_port = os.getenv("IPROYAL_SOCKS5_PORT", "32325")
        
    def get_organization_proxy_config(self, organization_id: str) -> Optional[Dict[str, Any]]:
        """
        Get proxy configuration for a specific organization
        
        Args:
            organization_id: The organization ID
            
        Returns:
            Dictionary with proxy configuration or None if not found
        """
        try:
            # Get proxy config from database
            result = (
                self.supabase.table("organization_proxy_configs")
                .select("*")
                .eq("organization_id", organization_id)
                .eq("is_active", True)
                .limit(1)
                .execute()
            )
            
            if not result.data:
                self.logger.warning(f"No proxy configuration found for organization {organization_id}")
                return None
                
            proxy_config = result.data[0]
            
            return {
                "proxy_username": proxy_config.get("proxy_username"),
                "proxy_password": proxy_config.get("proxy_password"),
                "proxy_host": proxy_config.get("proxy_host", self.iproyal_base_host),
                "http_port": proxy_config.get("http_port", self.iproyal_http_port),
                "socks5_port": proxy_config.get("socks5_port", self.iproyal_socks5_port),
                "proxy_type": proxy_config.get("proxy_type", "http"),
                "rotation_enabled": proxy_config.get("rotation_enabled", True),
                "session_duration": proxy_config.get("session_duration", "10m")
            }
            
        except Exception as e:
            self.logger.error(f"Error getting proxy config for organization {organization_id}: {str(e)}")
            return None
    
    def create_proxy_url(self, organization_id: str, proxy_type: str = "http") -> Optional[str]:
        """
        Create a proxy URL for the given organization
        
        Args:
            organization_id: The organization ID
            proxy_type: Type of proxy ("http" or "socks5")
            
        Returns:
            Proxy URL string or None if configuration not found
        """
        try:
            config = self.get_organization_proxy_config(organization_id)
            if not config:
                return None
                
            username = config["proxy_username"]
            password = config["proxy_password"]
            host = config["proxy_host"]
            
            # Generate unique session identifier for this scraping session
            session_id = f"org{organization_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Build proxy credentials with session management
            if config.get("rotation_enabled", True):
                # Use sticky sessions for better scraping consistency
                duration = config.get("session_duration", "10m")
                proxy_auth = f"{username}_session-{session_id}_lifetime-{duration}:{password}"
            else:
                proxy_auth = f"{username}:{password}"
            
            # Select port based on proxy type
            if proxy_type.lower() == "socks5":
                port = config["socks5_port"]
                proxy_url = f"socks5://{proxy_auth}@{host}:{port}"
            else:  # http/https
                port = config["http_port"]
                proxy_url = f"http://{proxy_auth}@{host}:{port}"
                
            self.logger.info(f"Created {proxy_type} proxy URL for organization {organization_id}")
            return proxy_url
            
        except Exception as e:
            self.logger.error(f"Error creating proxy URL for organization {organization_id}: {str(e)}")
            return None
    
    def get_proxy_dict_for_requests(self, organization_id: str) -> Optional[Dict[str, str]]:
        """
        Get proxy dictionary formatted for Python requests library
        
        Args:
            organization_id: The organization ID
            
        Returns:
            Dictionary with http and https proxy URLs for requests library
        """
        try:
            proxy_url = self.create_proxy_url(organization_id, "http")
            if not proxy_url:
                return None
                
            return {
                "http": proxy_url,
                "https": proxy_url
            }
            
        except Exception as e:
            self.logger.error(f"Error creating proxy dict for requests: {str(e)}")
            return None
    
    def get_proxy_for_selenium(self, organization_id: str) -> Optional[Dict[str, Any]]:
        """
        Get proxy configuration for Selenium WebDriver
        
        Args:
            organization_id: The organization ID
            
        Returns:
            Dictionary with proxy configuration for Selenium
        """
        try:
            config = self.get_organization_proxy_config(organization_id)
            if not config:
                return None
                
            # Generate session for this scraping run
            session_id = f"org{organization_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Build authentication
            if config.get("rotation_enabled", True):
                duration = config.get("session_duration", "10m")
                username = f"{config['proxy_username']}_session-{session_id}_lifetime-{duration}"
            else:
                username = config["proxy_username"]
                
            return {
                "proxy_type": "http",  # Selenium typically uses HTTP proxy type
                "host": config["proxy_host"],
                "port": config["http_port"],
                "username": username,
                "password": config["proxy_password"],
                "proxy_url": f"http://{username}:{config['proxy_password']}@{config['proxy_host']}:{config['http_port']}"
            }
            
        except Exception as e:
            self.logger.error(f"Error getting Selenium proxy config: {str(e)}")
            return None
    
    def create_organization_proxy_config(
        self, 
        organization_id: str, 
        proxy_username: str, 
        proxy_password: str,
        proxy_host: str = None,
        proxy_type: str = "http",
        rotation_enabled: bool = True,
        session_duration: str = "10m"
    ) -> bool:
        """
        Create or update proxy configuration for an organization
        
        Args:
            organization_id: The organization ID
            proxy_username: IPRoyal proxy username
            proxy_password: IPRoyal proxy password
            proxy_host: Proxy host (optional, uses default if not provided)
            proxy_type: Type of proxy ("http" or "socks5")
            rotation_enabled: Whether to use session rotation
            session_duration: Duration for sticky sessions
            
        Returns:
            True if successful, False otherwise
        """
        try:
            proxy_data = {
                "organization_id": organization_id,
                "proxy_username": proxy_username,
                "proxy_password": proxy_password,
                "proxy_host": proxy_host or self.iproyal_base_host,
                "http_port": self.iproyal_http_port,
                "socks5_port": self.iproyal_socks5_port,
                "proxy_type": proxy_type,
                "rotation_enabled": rotation_enabled,
                "session_duration": session_duration,
                "is_active": True,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # Check if configuration already exists
            existing = (
                self.supabase.table("organization_proxy_configs")
                .select("id")
                .eq("organization_id", organization_id)
                .execute()
            )
            
            if existing.data:
                # Update existing configuration
                result = (
                    self.supabase.table("organization_proxy_configs")
                    .update(proxy_data)
                    .eq("organization_id", organization_id)
                    .execute()
                )
                self.logger.info(f"Updated proxy configuration for organization {organization_id}")
            else:
                # Create new configuration
                result = (
                    self.supabase.table("organization_proxy_configs")
                    .insert(proxy_data)
                    .execute()
                )
                self.logger.info(f"Created proxy configuration for organization {organization_id}")
            
            return bool(result.data)
            
        except Exception as e:
            self.logger.error(f"Error creating/updating proxy config: {str(e)}")
            return False
    
    def test_proxy_connection(self, organization_id: str) -> bool:
        """
        Test proxy connection for an organization
        
        Args:
            organization_id: The organization ID
            
        Returns:
            True if proxy connection works, False otherwise
        """
        try:
            import requests
            
            proxy_dict = self.get_proxy_dict_for_requests(organization_id)
            if not proxy_dict:
                return False
                
            # Test connection with a simple HTTP request
            response = requests.get(
                "http://httpbin.org/ip", 
                proxies=proxy_dict, 
                timeout=10
            )
            
            if response.status_code == 200:
                response_data = response.json()
                self.logger.info(f"Proxy test successful for org {organization_id}. IP: {response_data.get('origin')}")
                return True
            else:
                self.logger.error(f"Proxy test failed for org {organization_id}. Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error testing proxy connection for org {organization_id}: {str(e)}")
            return False


class ProxyServiceSingleton:
    """Singleton for ProxyService"""
    _instance = None

    @classmethod
    def get_instance(cls) -> ProxyService:
        if cls._instance is None:
            cls._instance = ProxyService()
        return cls._instance 