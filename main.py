# file: main.py

import asyncio
import logging
import threading
import customtkinter as ctk
from pathlib import Path
from typing import Optional

import os
import sys

from core.service_locator import locator, ServiceLocator
from core.command_executor import CommandExecutor
from core.event_dispatcher import EventDispatcher
from core.plugin_manager import PluginManager
from core.api_manager import ApiManager
from core.context_manager import ContextManager
from core.role_selector import RoleSelector
from core.agent import Agent
# --- ADD THESE IMPORTS ---
from core.error_analytics import ErrorAnalytics
from utils.error_reporter import get_reporter, BaseErrorReporter
# --- END ADD ---
from core.memory_manager import MemoryManager

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

        self._restart_requested = False
        
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

    # --- ADD THESE TWO METHODS ---
    def restart(self):
        """Sets a flag to restart and then quits the application."""
        # Set the flag so the main thread knows to restart
        self.locator.resolve("logger").info("Restart requested by user.")
        self._restart_requested = True
        # Call quit() to gracefully shut down the main loop
        self.quit()
            
    def quit(self):
        """
        Gracefully shuts down all windows and the main tkinter loop.
        """
        # --- ADD THIS ---
        # Explicitly destroy child windows first to prevent race conditions
        try:
            if self.popup_window:
                self.popup_window.destroy()
            if self.settings_window:
                self.settings_window.destroy()
        except Exception as e:
            # Log any errors during child window destruction
            logging.warning(f"Error destroying child windows: {e}")
        # --- END ADD ---

        # Now, destroy the main root window
        self.destroy()

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
        memory_manager: MemoryManager = self.locator.resolve("memory_manager")

        # NEW: Start the dispatcher loop so async events are processed
        event_dispatcher.start()
        # Start memory monitoring
        memory_manager.start_monitoring()

        try:
            # --- MODIFIED ---
            await plugin_manager.discover_and_load_plugins()
            logger.info("Plugin discovery/load process complete.")
            # --- END MODIFIED ---
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
    
    # Register ConfigLoader as a singleton
    # --- MODIFIED: Use a reliable path for configs ---
    # Use platform-specific app data directory
    app_data_dir = Path(os.getenv("APPDATA") or Path.home() / ".config" / "PersonalAIAgent") / "config"
    locator_instance.register("config_loader", lambda: ConfigLoader(app_data_dir), singleton=True)
    # --- END MODIFIED ---
    
    # Register EventDispatcher as a singleton, now with its dependency
    locator_instance.register("event_dispatcher", lambda: EventDispatcher(locator_instance.resolve("config_loader")), singleton=True)
    
    # Register MemoryManager as a singleton
    locator_instance.register("memory_manager", lambda: MemoryManager(locator_instance), singleton=True)
    
    # Register PluginManager as a singleton.
    locator_instance.register("plugin_manager", lambda: PluginManager(locator_instance), singleton=True)
    
    # --- NEW FOR PHASE 3 ---
    
    # Register ApiManager
    locator_instance.register("api_manager", lambda: ApiManager(locator_instance), singleton=True)
    
    # Register ContextManager
    locator_instance.register("context_manager", lambda: ContextManager(locator_instance), singleton=True)
    
    # Register RoleSelector
    locator_instance.register("role_selector", lambda: RoleSelector(locator_instance), singleton=True)

    # Register the Agent (which depends on the above)
    locator_instance.register("agent", lambda: Agent(locator_instance), singleton=True)

    # --- NEW FOR PHASE 4 ---
    locator_instance.register("command_executor", lambda: CommandExecutor(locator_instance), singleton=True)
    
    # --- ADDED: Error Analytics Services ---
    # Register the reporter (factory function)
    locator_instance.register(
        "error_reporter", 
        lambda: get_reporter(locator_instance.resolve("config_loader")), 
        singleton=True
    )
    # Register the analytics service
    locator_instance.register(
        "error_analytics", 
        lambda: ErrorAnalytics(
            locator_instance.resolve("config_loader").get_config("error_analytics_config.json"),
            locator_instance.resolve("error_reporter")
        ), 
        singleton=True
    )
    # --- END ADDED ---
    
    # --- ADDED: Register logger as a service ---
    # This allows other services to log during initialization
    # Note: We configure it *after* config is loaded, but register it here.
    locator_instance.register("logger", lambda: logging.getLogger(), singleton=True)
    # --- END ADDED ---


if __name__ == "__main__":
    # 1. Register synchronous services first
    register_core_services(locator)
    
    # 2. Load config and set up logging
    config_loader: ConfigLoader = locator.resolve("config_loader")
    config_loader.load_all_configs()
    
    # --- MODIFIED: Setup logging WITH analytics service ---
    analytics_service: ErrorAnalytics = locator.resolve("error_analytics")
    setup_logging(config_loader, analytics_service)
    # --- END MODIFIED ---
    
    # --- NEW: Apply theme from config ---
    theme = config_loader.get("ui_config.json", "theme", "System")
    ctk.set_appearance_mode(theme.lower())
    # --- END NEW ---

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
    args = ["uv", "run", "main.py"]
    # --- MODIFIED: Robust Restart Logic ---
    if app._restart_requested:
        logging.info("Restart requested. Relaunching application...")
        try:
            # Relaunch the script using the same executable and arguments
            # This is more robust than hardcoding 'uv run main.py'
            os.execvp(args[0], args)
        except Exception as e:
            logging.error(f"Failed to restart: {e}", exc_info=True)
    else:
        logging.info("Exiting normally.")
    # --- END MODIFIED ---