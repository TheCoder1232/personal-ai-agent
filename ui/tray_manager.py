# file: ui/tray_manager.py

import pystray
from PIL import Image
from pathlib import Path
import threading
from core.service_locator import locator
from core.event_dispatcher import EventDispatcher

class TrayManager:
    """
    Manages the system tray icon and its menu.
    Runs in a separate thread to not block the main UI.
    """
    def __init__(self, app):
        self.app = app
        self.locator = locator
        self.events: EventDispatcher = self.locator.resolve("event_dispatcher")
        
        self.icon_path = Path(__file__).parent.parent / "assets" / "icons" / "icon.png"
        self.icon_image = Image.open(self.icon_path)
        
        self.menu = pystray.Menu(
            pystray.MenuItem("Open Chat", self.on_open_chat, default=True),
            pystray.MenuItem("Settings", self.on_open_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self.on_quit)
        )
        
        self.icon = pystray.Icon("PersonalAIAgent", self.icon_image, "Personal AI Agent", self.menu)

    def start(self):
        """Starts the pystray icon in a separate thread."""
        # pystray.Icon.run() is blocking, so it needs its own thread
        thread = threading.Thread(target=self.icon.run, daemon=True)
        thread.start()

    def on_open_chat(self):
        """
        Publishes an event to open the chat window.
        This is called from the pystray thread.
        """
        # We don't need to wrap this in an async call since the App's
        # .show_popup_window method uses .after() to make it thread-safe.
        self.app.show_popup_window()

    def on_open_settings(self):
        """
        Publishes an event to open the settings window.
        This is called from the pystray thread.
        """
        self.app.show_settings_window()

    def on_quit(self):
        """Stops the tray icon and exits the application."""
        self.icon.stop()
        self.app.quit() # Shuts down the main tkinter loop