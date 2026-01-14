"""
Dependency Injection Container to manage service dependencies and break circular imports.
"""

import threading
from typing import Dict, Any, Type, Optional

class DependencyContainer:
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        self._services = {}
        self._factories = {}
        self._lazy_initializers = {}
    
    def register_service(self, service_name: str, service_instance: Any) -> None:
        """Register an existing service instance."""
        self._services[service_name] = service_instance
    
    def register_factory(self, service_name: str, factory_func: callable) -> None:
        """Register a factory function that creates the service on demand."""
        self._factories[service_name] = factory_func
    
    def register_lazy_initializer(self, service_name: str, service_class: Type, *args, **kwargs) -> None:
        """Register a service to be lazily initialized on first access."""
        self._lazy_initializers[service_name] = (service_class, args, kwargs)
    
    def get_service(self, service_name: str) -> Optional[Any]:
        """Get or create a service by name."""
        # Return existing instance if available
        if service_name in self._services:
            return self._services[service_name]
        
        # Try to create from factory if registered
        if service_name in self._factories:
            service = self._factories[service_name]()
            self._services[service_name] = service
            return service
        
        # Try to create from lazy initializer if registered
        if service_name in self._lazy_initializers:
            service_class, args, kwargs = self._lazy_initializers[service_name]
            service = service_class(*args, **kwargs)
            self._services[service_name] = service
            return service
        
        return None 