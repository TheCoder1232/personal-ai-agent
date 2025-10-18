# file: plugins/demo_plugin.py

import logging
from plugins import PluginBase
from core.service_locator import ServiceLocator
from core.event_dispatcher import EventDispatcher

class DemoPlugin(PluginBase):
    """
    A simple plugin to demonstrate the plugin and event systems.
    It listens for a "demo.greet" event and logs a message.
    """
    
    def __init__(self, service_locator: ServiceLocator):
        super().__init__(service_locator)
        # Get the services this plugin needs from the locator
        self.events: EventDispatcher = self.locator.resolve("event_dispatcher")
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("DemoPlugin instance created.")

    def get_metadata(self):
        return {
            "name": "DemoPlugin",
            "version": "1.0.0",
            "description": "A plugin to demonstrate the core architecture."
        }

    def initialize(self):
        """Called when the plugin is first loaded."""
        # Subscribe to a custom event
        self.events.subscribe("DEMO_EVENT.GREET", self.on_greet)
        self.logger.info("DemoPlugin initialized and subscribed to GREET event.")

    async def on_greet(self, name: str):
        """Async event handler for the GREET event."""
        self.logger.info(f"GREETING RECEIVED! Hello, {name}!")
        # We can even publish a reply event
        await self.events.publish("DEMO_EVENT.GREETING_SENT", plugin="DemoPlugin")
        
    def start(self):
        self.logger.info("DemoPlugin started.")

    def stop(self):
        self.logger.info("DemoPlugin stopped.")