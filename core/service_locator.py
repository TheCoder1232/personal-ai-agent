# file: core/service_locator.py

import inspect
from typing import Callable, Any, Dict, Optional

class ServiceLocator:
    """
    A simple dependency injection container (Service Locator pattern).
    It manages service registration and resolution, supporting
    singleton and transient lifetimes.
    """
    def __init__(self):
        # Stores singleton instances
        self._singletons: Dict[str, Any] = {}
        # Stores factories for all services
        self._factories: Dict[str, Callable[[], Any]] = {}
        # Tracks which services are singletons
        self._is_singleton: Dict[str, bool] = {}

    def register(self, name: str, factory: Callable[[], Any], singleton: bool = True):
        """
        Registers a service with the locator.

        Args:
            name (str): The unique name to identify the service.
            factory (Callable): A function (or class) that creates an instance 
                                of the service.
            singleton (bool): If True, only one instance is ever created (on first
                              request). If False, a new instance is created
                              every time it's resolved (transient).
        """
        if name in self._factories:
            print(f"Warning: Service '{name}' is being re-registered.")
            
        self._factories[name] = factory
        self._is_singleton[name] = singleton
        
        # Eagerly clear old singleton instance if re-registering
        if name in self._singletons:
            del self._singletons[name]

    def resolve(self, name: str) -> Any:
        """
        Resolves (gets) a service instance by its name.
        
        Handles constructor injection by inspecting the factory's signature
        and resolving its dependencies automatically.
        """
        if self._is_singleton.get(name):
            # Case 1: Singleton. Return existing instance or create/store it.
            if name not in self._singletons:
                self._singletons[name] = self._create_instance(name)
            return self._singletons[name]
        
        # Case 2: Transient. Always create a new instance.
        if name in self._factories:
            return self._create_instance(name)

        raise KeyError(f"Service '{name}' not found.")

    def _create_instance(self, name: str) -> Any:
        """Internal helper to create an instance from a factory."""
        factory = self._factories.get(name)
        if not factory:
            raise KeyError(f"Factory for service '{name}' not found.")
        
        # --- Constructor Injection ---
        # Inspect the factory's (e.g., class __init__) arguments
        try:
            sig = inspect.signature(factory)
            dependencies = {}
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                
                # Assume the parameter name is the service name
                # e.g., def __init__(self, event_dispatcher: EventDispatcher):
                # We will try to resolve 'event_dispatcher'
                try:
                    dependencies[param_name] = self.resolve(param_name)
                except KeyError:
                    # If it's not a resolvable service, it might be a 
                    # regular arg with a default value. If not, this will fail.
                    if param.default == inspect.Parameter.empty:
                         raise TypeError(
                             f"Cannot resolve dependency '{param_name}' for service '{name}'. "
                             "Ensure it's registered or has a default value."
                         )
            
            # Create the instance, injecting resolved dependencies
            return factory(**dependencies)
        
        except (ValueError, TypeError) as e:
            # Handle non-class factories or factories with no args
            if "no signature" in str(e) or not sig.parameters:
                 return factory()
            else:
                 print(f"Error inspecting factory for '{name}': {e}")
                 # Fallback to simple call, may fail if deps are needed
                 return factory()

    def __getitem__(self, name: str) -> Any:
        """Allows dictionary-style access, e.g., locator['logger']"""
        return self.resolve(name)

    def __contains__(self, name: str) -> bool:
        """Allows 'in' check, e.g., 'logger' in locator"""
        return name in self._factories

# Create a single, global instance to be used everywhere
# This is a common pattern for a Service Locator.
locator = ServiceLocator()