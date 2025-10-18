# file: ui/settings_window.py

import logging
import asyncio
import customtkinter as ctk
from core.service_locator import locator
from core.event_dispatcher import EventDispatcher
from utils.config_loader import ConfigLoader

class SettingsWindow(ctk.CTkToplevel):
    """
    The main settings window with multiple tabs.
    """
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.locator = locator
        self.events: EventDispatcher = self.locator.resolve("event_dispatcher")
        self.config: ConfigLoader = self.locator.resolve("config_loader")
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.title("Settings")
        self.geometry("600x400")
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- Create Tab View ---
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Add tabs as per the plan
        self.tab_view.add("API Keys")
        self.tab_view.add("Models")
        self.tab_view.add("Hotkeys")
        self.tab_view.add("Plugins")
        self.tab_view.add("MCP Servers")
        self.tab_view.add("Logs")
        
        # --- Populate Tabs (Stubbed) ---
        self.create_api_keys_tab(self.tab_view.tab("API Keys"))
        self.create_models_tab(self.tab_view.tab("Models"))
        self.create_hotkeys_tab(self.tab_view.tab("Hotkeys"))
        self.create_plugins_tab(self.tab_view.tab("Plugins"))
        # (Other tabs can be added here)

        # --- Save/Close Buttons ---
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="se")
        
        self.save_button = ctk.CTkButton(self.button_frame, text="Save", command=self.save_settings)
        self.save_button.pack(side="left", padx=5)
        
        self.close_button = ctk.CTkButton(self.button_frame, text="Close", command=self.hide)
        self.close_button.pack(side="left", padx=5)

        self.withdraw() # Hide at start
        self.protocol("WM_DELETE_WINDOW", self.hide)
        self.is_visible = False

    def create_api_keys_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)
        
        # Gemini
        ctk.CTkLabel(tab, text="Gemini API Key:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.gemini_key_entry = ctk.CTkEntry(tab, show="*")
        self.gemini_key_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(tab, text="Test", command=lambda: self.test_connection("gemini")).grid(row=0, column=2, padx=10, pady=10)
        
        # OpenRouter
        ctk.CTkLabel(tab, text="OpenRouter API Key:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.openrouter_key_entry = ctk.CTkEntry(tab, show="*")
        self.openrouter_key_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(tab, text="Test", command=lambda: self.test_connection("openrouter")).grid(row=1, column=2, padx=10, pady=10)

        # Ollama
        ctk.CTkLabel(tab, text="Ollama Base URL:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.ollama_url_entry = ctk.CTkEntry(tab)
        self.ollama_url_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(tab, text="Test", command=lambda: self.test_connection("ollama")).grid(row=2, column=2, padx=10, pady=10)

    def create_models_tab(self, tab):
        ctk.CTkLabel(tab, text="Model settings (coming in Phase 3)").pack(padx=20, pady=20)

    def create_hotkeys_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(tab, text="Open Chat:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.hotkey_chat_entry = ctk.CTkEntry(tab)
        self.hotkey_chat_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(tab, text="Screen Capture:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.hotkey_screen_entry = ctk.CTkEntry(tab)
        self.hotkey_screen_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

    def create_plugins_tab(self, tab):
        ctk.CTkLabel(tab, text="Plugin management (coming soon)").pack(padx=20, pady=20)
        # We will populate this from plugin_manager.get_all_plugins()

    def load_settings(self):
        """Loads all settings from config files into the UI fields."""
        models_config = self.config.get_config("models_config.json")
        self.gemini_key_entry.insert(0, models_config.get("providers", {}).get("gemini", {}).get("api_key", ""))
        self.openrouter_key_entry.insert(0, models_config.get("providers", {}).get("openrouter", {}).get("api_key", ""))
        self.ollama_url_entry.insert(0, models_config.get("providers", {}).get("ollama", {}).get("base_url", "http://localhost:11434"))
        
        system_config = self.config.get_config("system_config.json")
        self.hotkey_chat_entry.insert(0, system_config.get("hotkeys", {}).get("open_chat", "<ctrl>+<shift>+<space>"))
        self.hotkey_screen_entry.insert(0, system_config.get("hotkeys", {}).get("screen_capture", "<ctrl>+<shift>+x"))

    def save_settings(self):
        """Saves all settings from the UI fields back to config files."""
        self.logger.info("Saving settings...")
        
        # Save models config
        models_config = self.config.get_config("models_config.json")
        models_config["providers"]["gemini"]["api_key"] = self.gemini_key_entry.get()
        models_config["providers"]["openrouter"]["api_key"] = self.openrouter_key_entry.get()
        models_config["providers"]["ollama"]["base_url"] = self.ollama_url_entry.get()
        self.config.save_config("models_config.json", models_config)
        
        # Save system config
        system_config = self.config.get_config("system_config.json")
        system_config["hotkeys"]["open_chat"] = self.hotkey_chat_entry.get()
        system_config["hotkeys"]["screen_capture"] = self.hotkey_screen_entry.get()
        self.config.save_config("system_config.json", system_config)

        # Publish an event so other services (like HotkeyManager) can reload
        self.publish_async_event("UI_EVENT.SETTINGS_CHANGED")
        self.hide()

    def test_connection(self, provider: str):
        """Publishes an event to test an API connection."""
        self.logger.info(f"Requesting connection test for: {provider}")
        # Phase 3's ApiManager will listen for this
        self.publish_async_event(f"API_EVENT.TEST_CONNECTION", provider=provider)
        
    def publish_async_event(self, event_type: str, *args, **kwargs):
        """Safely publishes an event to the asyncio loop from the UI thread."""
        async_loop = getattr(self.master, "async_loop", None)
        if not async_loop:
            self.logger.warning("Async loop not available. Cannot publish event.")
            return
        
        coro = self.events.publish(event_type, *args, **kwargs)
        asyncio.run_coroutine_threadsafe(coro, async_loop)

    def show(self):
        """Loads settings and shows the window."""
        self.load_settings() # Load fresh data each time
        self.deiconify()
        self.lift()
        self.focus_force()
        self.is_visible = True
        
    def hide(self):
        self.withdraw()
        self.is_visible = False