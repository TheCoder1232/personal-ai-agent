# file: main.py

import asyncio
import logging
import threading
import customtkinter as ctk
from pathlib import Path
from typing import Optional

from core.service_locator import locator, ServiceLocator
from core.event_dispatcher import EventDispatcher
from core.plugin_manager import PluginManager
from utils.config_loader import ConfigLoader
from utils.logger import setup_logging

# Import the new UI and input classes (we'll create these next)
from ui.tray_manager import TrayManager
from ui.popup_window import PopupWindow
from ui.settings_window import SettingsWindow
from input.hotkey_manager import HotkeyManager
from ui.notification import NotificationManager

class PersonalAIAgentApp(ctk.CTk):
    """
    The main application class, inheriting from CustomTkinter.
    This class manages the main UI thread and coordinates with the
    background asyncio thread.
    """
    def __init__(self, locator):
        super().__init__()
        self.locator = locator
        # We hide the main root window; the app lives in the tray
        self.withdraw() 
        
        self.settings_window: Optional[SettingsWindow] = None
        self.popup_window: Optional[PopupWindow] = None
        
        # This will hold the asyncio loop running in the background thread
        self.async_loop = None
        self.async_loop = None
        
        # Register the app itself in the locator so other services can use it
        # e.g., to open windows from a background thread
        self.locator.register("app", lambda: self, singleton=True)

    def initialize_services(self):
        """
        Initializes all core UI and input services.
        This is called after the async loop is available.
        """
        # --- Initialize UI Components ---
        # Note: We pass 'self' (the app) to windows so they can be
        # transient_for (appear on top of) the (hidden) root window.
        
        # We create instances but don't show them yet
        self.settings_window = SettingsWindow(self)
        self.popup_window = PopupWindow(self)
        self.notification_manager = NotificationManager(self)
        
        # --- Initialize Tray Manager ---
        # The tray manager is special; it runs in its own thread
        self.tray_manager = TrayManager(self)
        self.tray_manager.start()

        # --- Initialize Hotkey Manager ---
        # Ensure the asyncio loop has been set by the background thread before
        # constructing the HotkeyManager. The assert narrows the type for static
        # type checkers and provides a clear runtime error if the assumption is broken.
        assert self.async_loop is not None, "Async loop must be initialized before initializing services"
        self.hotkey_manager = HotkeyManager(self.locator, self.async_loop)
        self.hotkey_manager.start_listener()

        # --- Subscribe to UI Events ---
        events: EventDispatcher = self.locator.resolve("event_dispatcher")
        events.subscribe("UI_EVENT.OPEN_CHAT", self.show_popup_window)
        events.subscribe("UI_EVENT.OPEN_SETTINGS", self.show_settings_window)
    def show_popup_window(self, *args, **kwargs):
        """Thread-safe method to show the popup window."""
        # Use .after() to schedule UI changes from any thread.
        # Wrap the call so we safely create the window if it doesn't exist yet
        def _show():
            if self.popup_window is None:
                self.popup_window = PopupWindow(self)
            self.popup_window.show()
        self.after(0, _show)

    def show_settings_window(self, *args, **kwargs):
        """Thread-safe method to show the settings window."""
        # Wrap the call so we safely create the window if it doesn't exist yet
        def _show_settings():
            if self.settings_window is None:
                self.settings_window = SettingsWindow(self)
            self.settings_window.show()
        self.after(0, _show_settings)

    def start_asyncio_loop(self):
        """Runs the main asyncio event loop in a separate thread."""
        self.async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.async_loop)
        
        # Run the async_main coroutine
        self.async_loop.run_until_complete(self.async_main())
        self.async_loop.run_forever()

    async def async_main(self):
        """
        The main entry point for all asynchronous tasks.
        This is essentially the 'main' function from Phase 1.
        """
        logger = logging.getLogger(__name__)
        logger.info("Asyncio background thread started.")
        
        # Get services that were registered in the main thread
        plugin_manager: PluginManager = self.locator.resolve("plugin_manager")
        event_dispatcher: EventDispatcher = self.locator.resolve("event_dispatcher")

        try:
            await plugin_manager.load_plugins()
            logger.info(f"Loaded {len(plugin_manager.loaded_plugins)} plugins.")
        except Exception as e:
            logger.error(f"Failed to load plugins: {e}", exc_info=True)
            return

        # Now that the async loop is running and plugins are loaded,
        # we tell the main thread to finish initializing its UI components
        # (like hotkeys) that depend on the async loop.
        self.after(0, self.initialize_services)
        
        # (DEMO) Test the event system from Phase 1
        async def on_greeting_sent(plugin: str):
            logger.info(f"Main async received reply: Greeting was sent by {plugin}!")
            # Test the notification system
            await event_dispatcher.publish(
                "NOTIFICATION_EVENT.INFO", 
                title="Plugin Loaded",
                message=f"{plugin} successfully loaded and responded."
            )
        
        event_dispatcher.subscribe("DEMO_EVENT.GREETING_SENT", on_greeting_sent)
        
        logger.info("Publishing DEMO_EVENT.GREET...")
        await event_dispatcher.publish("DEMO_EVENT.GREET", name="Async World")
        logger.info("Async_main setup complete. Waiting for events.")


def register_core_services(locator_instance: ServiceLocator):
    """Registers all non-async services in the service locator."""
    
    # Register EventDispatcher as a singleton
    locator_instance.register("event_dispatcher", EventDispatcher, singleton=True)
    
    # Register ConfigLoader as a singleton
    config_path = Path(__file__).parent / "config"
    locator_instance.register("config_loader", lambda: ConfigLoader(config_path), singleton=True)
    
    # Register PluginManager as a singleton.
    locator_instance.register("plugin_manager", lambda: PluginManager(locator_instance), singleton=True)


if __name__ == "__main__":
    # 1. Register synchronous services first
    register_core_services(locator)
    
    # 2. Load config and set up logging
    config_loader: ConfigLoader = locator.resolve("config_loader")
    config_loader.load_all_configs()
    setup_logging(config_loader)
    
    # 3. Create the main application instance
    app = PersonalAIAgentApp(locator)
    
    # 4. Start the background asyncio thread
    async_thread = threading.Thread(
        target=app.start_asyncio_loop, 
        daemon=True # Daemon threads exit when the main thread exits
    )
    async_thread.start()
    
    # 5. Start the CustomTkinter main loop (this is blocking)
    # This MUST run in the main thread
    logging.info("Starting CustomTkinter main loop...")
    app.mainloop()
    
    logging.info("Application shutting down.")