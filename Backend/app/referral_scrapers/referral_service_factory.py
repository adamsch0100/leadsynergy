from typing import Dict, Any, Optional, Type
import importlib
import os
import logging

from app.models.lead import Lead

class ReferralServiceFactory:
    """
    Factory class for creating appropriate referral service instances
    based on the lead source
    """
    
    _services = {} # Class-level cache of service classes
    _logger = logging.getLogger(__name__)
    
    @classmethod
    def get_service(cls, source_name: str, lead:Lead) -> Optional[Any]:
        # Normalized source name for file/module lookup
        normalized_name = source_name.lower().replace(' ', '_')
        
        # Check if we've already loaded this service
        if normalized_name in cls._services:
            service_class = cls._services[normalized_name]
            return service_class(lead=lead)
        
        # Try to dynamically import the service class
        try:
            # Path to the expected module
            module_path  = f"app.referral_scrapers.{normalized_name}.{normalized_name}_service"
            
            # Try to import the module
            try:
                module = importlib.import_module(module_path)
            except ImportError:
                cls._logger.error(f"Could not import module for {source_name}: {module_path}")
                return None
            
            # Look for the service class (expected to be SourceNameService)
            class_name = f"{source_name.replace(' ', '')}Service"
            service_class = getattr(module, class_name, None)
            
            if service_class:
                # Cache the class for future use
                cls._services[normalized_name] = service_class
                return service_class(lead)
            
            cls._logger.error(f"Could not find service class {class_name} in {module_path}")
            return None
        
        except Exception as e:
            cls._logger.error(f"Error loading service for {source_name}: {str(e)}")
            return None
        
    
    @classmethod
    def service_exists(cls, source_name: str) -> bool:
        normalized_name = source_name.lower().replace(' ', '_')
        
        # Check our cache first
        if normalized_name in cls._services:
            return True
        
        # Look for the module file
        try:
            # Get the base directory for referral scrapers
            import inspect
            import os
            
            current_file = inspect.getfile(cls)
            base_dir = os.path.dirname(current_file)
            
            # Check if the directory and service file exists
            service_dir = os.path.join(base_dir, normalized_name)
            service_file = os.path.join(service_dir, f"{normalized_name}_service.py")
            
            return os.path.isdir(service_dir) and os.path.isfile(service_file)
        
        except Exception as e:
            cls._logger.error(f"Error checking if service exists for {source_name}: {str(e)}")
            return False
    