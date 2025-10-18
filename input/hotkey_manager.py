# file: input/hotkey_manager.py

import logging
import asyncio
from pynput import keyboard
from core.service_locator import ServiceLocator
from core.event_dispatcher import EventDispatcher
from utils.config_loader import ConfigLoader

class HotkeyManager:
    """
    Manages global hotkeys using pynput.
    Listens in a separate thread and dispatches events to the
    asyncio event loop.
    """
    def __init__(self, locator: ServiceLocator, async_loop: asyncio.AbstractEventLoop):
        self.locator = locator
        self.async_loop = async_loop # The loop from the background thread
        self.events: EventDispatcher = self.locator.resolve("event_dispatcher")
        self.config: ConfigLoader = self.locator.resolve("config_loader")
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.hotkeys_config = self.config.get("system_config.json", "hotkeys", {})
        self.listener = None

    def on_open_chat(self):
        """Handler for the 'open_chat' hotkey."""
        self.logger.info("'Open Chat' hotkey pressed.")
        self.publish_async_event("UI_EVENT.OPEN_CHAT")

    def on_screen_capture(self):
        """Handler for the 'screen_capture' hotkey."""
        self.logger.info("'Screen Capture' hotkey pressed.")
        self.publish_async_event("PLUGIN_EVENT.SCREEN_CAPTURE")

    def publish_async_event(self, event_type: str, *args, **kwargs):
        """
        Safely publishes an event to the asyncio loop from this (pynput) thread.
        """
        if not self.async_loop:
            self.logger.warning("Async loop not available. Cannot publish event.")
            return
            
        # Create a coroutine
        coro = self.events.publish(event_type, *args, **kwargs)
        
        # Schedule the coroutine to run on the asyncio event loop
        asyncio.run_coroutine_threadsafe(coro, self.async_loop)

    def start_listener(self):
        """Starts the global hotkey listener."""
        try:
            hotkey_map = {
                self.hotkeys_config.get("open_chat"): self.on_open_chat,
                self.hotkeys_config.get("screen_capture"): self.on_screen_capture
            }
            
            # Filter out any unconfigured hotkeys
            active_hotkeys = {k: v for k, v in hotkey_map.items() if k}
            
            if not active_hotkeys:
                self.logger.warning("No hotkeys configured.")
                return

            self.logger.info(f"Starting hotkey listener with keys: {list(active_hotkeys.keys())}")
            
            # The pynput.keyboard.GlobalHotKeys listener runs in its own thread
            self.listener = keyboard.GlobalHotKeys(active_hotkeys)
            self.listener.start()
            
        except Exception as e:
            self.logger.error(f"Failed to start hotkey listener: {e}", exc_info=True)

    def stop_listener(self):
        if self.listener:
            self.logger.info("Stopping hotkey listener.")
            self.listener.stop()