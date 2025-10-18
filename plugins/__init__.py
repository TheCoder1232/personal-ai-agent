# file: plugins/__init__.py

from abc import ABC, abstractmethod
from typing import Dict, Any
from core.service_locator import ServiceLocator

class PluginBase(ABC):
    """
    Abstract Base Class for all plugins.
    
    Defines the contract that all plugins must adhere to.
    Plugins are instantiated with the global service locator
    to allow them to access core services like the event dispatcher
    or config loader.
    """
    
    def __init__(self, service_locator: ServiceLocator):
        self.locator = service_locator
        # Plugins can get services they need during init
        # e.g., self.events = self.locator.resolve("event_dispatcher")
        # e.g., self.config = self.locator.resolve("config_loader")

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """
        Returns metadata about the plugin.
        
        Expected keys:
        - "name": (str) The display name of the plugin.
        - "version": (str) The plugin's version.
        - "description": (str) A brief description.
        """
        pass

    @abstractmethod
    def initialize(self):
        """
        Called once when the plugin is loaded.
        This is the place to subscribe to events.
        """
        pass

    def start(self):
        """
        Called when the plugin is enabled (e.g., from settings).
        Can be used to start background tasks.
        """
        pass # Optional to implement

    def stop(self):
        """
        Called when the plugin is disabled.
        Should clean up any resources or tasks.
        """
        pass # Optional to implement