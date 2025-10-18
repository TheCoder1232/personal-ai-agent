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
        self.geometry("600x480") # --- Increased height for new options
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- NEW: Staging for model list edits ---
        # This holds a temporary copy of the model lists while we edit them.
        # This prevents losing edits if you switch provider tabs before saving.
        self.staged_model_lists = {}

        # --- NEW: StringVars for active provider/model dropdowns ---
        self.provider_var = ctk.StringVar()
        self.model_var = ctk.StringVar()
        
        # --- NEW: Theme variable (from a3) ---
        self.theme_var = ctk.StringVar()

        # --- Create Tab View ---
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Add tabs as per the plan (Merged from a2 and a3)
        self.tab_view.add("General") # --- Added from a3
        self.tab_view.add("Models") # --- Swapped to be the first tab (in a2)
        self.tab_view.add("API Keys")
        self.tab_view.add("Hotkeys")
        self.tab_view.add("Plugins")
        self.tab_view.add("MCP Servers") # --- Kept from a2
        
        # --- Populate Tabs ---
        self.create_general_tab(self.tab_view.tab("General")) # --- Added from a3
        self.create_models_tab(self.tab_view.tab("Models"))
        self.create_api_keys_tab(self.tab_view.tab("API Keys"))
        self.create_hotkeys_tab(self.tab_view.tab("Hotkeys"))
        self.create_plugins_tab(self.tab_view.tab("Plugins"))

        # --- Save/Close Buttons ---
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="e")
        
        self.save_button = ctk.CTkButton(self.button_frame, text="Save", command=self.save_settings)
        self.save_button.pack(side="left", padx=5)
        
        self.close_button = ctk.CTkButton(self.button_frame, text="Close", command=self.hide)
        self.close_button.pack(side="left", padx=5)

        self.withdraw() # Hide at start
        self.protocol("WM_DELETE_WINDOW", self.hide)
        self.is_visible = False
        
        # --- NEW: Trace provider changes ---
        # This makes the "Active Model" dropdown and "Manage Models" list
        # update automatically when you change the "Active Provider".
        self.provider_var.trace_add("write", self._on_provider_changed)
        
        # --- NEW: Bind to geometry changes for saving (from a3) ---
        self.bind("<Configure>", self._on_window_move)
        self.last_geometry = ""

    # --- NEW: General Tab (from a3) ---
    def create_general_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(tab, text="Theme:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        theme_menu = ctk.CTkOptionMenu(tab, variable=self.theme_var, values=["System", "Dark", "Light"])
        theme_menu.grid(row=0, column=1, padx=10, pady=10, sticky="w")

    # --- NEW: Fully implemented Models Tab ---
    def create_models_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)

        # --- Active Model Selection ---
        ctk.CTkLabel(tab, text="Active Provider:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.provider_dropdown = ctk.CTkOptionMenu(tab, variable=self.provider_var)
        self.provider_dropdown.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(tab, text="Active Model:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.model_dropdown = ctk.CTkOptionMenu(tab, variable=self.model_var)
        self.model_dropdown.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        # --- Separator ---
        ctk.CTkLabel(tab, text="Manage Models", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, columnspan=2, padx=10, pady=(10,0), sticky="w")
        ctk.CTkFrame(tab, height=2).grid(row=3, column=0, columnspan=2, padx=10, pady=(5,10), sticky="ew") # visual separator

        # --- Model Management UI ---
        self.model_list_frame = ctk.CTkScrollableFrame(tab)
        self.model_list_frame.grid(row=4, column=0, columnspan=2, padx=10, pady=0, sticky="nsew")
        tab.grid_rowconfigure(4, weight=1) # Make the list frame expand

        add_frame = ctk.CTkFrame(tab)
        add_frame.grid(row=5, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        add_frame.grid_columnconfigure(0, weight=1)

        self.new_model_entry = ctk.CTkEntry(add_frame, placeholder_text="e.g., ollama/llama3-8b")
        self.new_model_entry.grid(row=0, column=0, padx=(0, 5), pady=0, sticky="ew")
        self.new_model_entry.bind("<Return>", self._add_model_to_ui)

        self.add_model_button = ctk.CTkButton(add_frame, text="Add Model", width=100, command=self._add_model_to_ui)
        self.add_model_button.grid(row=0, column=1, padx=(5, 0), pady=0)

    # --- NEW: Callback when provider dropdown changes ---
    def _on_provider_changed(self, *args):
        """Called when self.provider_var changes."""
        provider_id = self.provider_var.get()
        if provider_id:
            self._update_model_ui(provider_id)

    # --- NEW: Updates the model UI ---
    def _update_model_ui(self, provider_id: str):
        """
        Updates the "Active Model" dropdown and "Manage Models" list
        based on the selected provider.
        """
        self.logger.debug(f"Updating model UI for provider: {provider_id}")
        
        # 1. Get the list of models from our staging variable
        models_list = self.staged_model_lists.get(provider_id, [])
        
        # 2. Update "Active Model" dropdown
        if models_list:
            self.model_dropdown.configure(values=models_list)
            # Set dropdown to first item, but DON'T set self.model_var yet.
            # self.model_var should only be set from load_settings or by user.
            current_active_model = self.model_var.get()
            if current_active_model not in models_list:
                self.model_var.set(models_list[0])
        else:
            self.model_dropdown.configure(values=["No models found"])
            self.model_var.set("No models found")

        # 3. Clear and rebuild the "Manage Models" list
        for widget in self.model_list_frame.winfo_children():
            widget.destroy()
            
        for model_name in models_list:
            frame = ctk.CTkFrame(self.model_list_frame)
            frame.pack(fill="x", expand=True, padx=5, pady=2)
            frame.grid_columnconfigure(0, weight=1)

            label = ctk.CTkLabel(frame, text=model_name)
            label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

            remove_button = ctk.CTkButton(
                frame, 
                text="X", 
                width=30, 
                command=lambda p=provider_id, m=model_name: self._remove_model_from_ui(p, m)
            )
            remove_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")

    # --- NEW: Adds a model to the staged list and UI ---
    def _add_model_to_ui(self, event=None):
        provider_id = self.provider_var.get()
        new_model = self.new_model_entry.get().strip()
        
        if not provider_id:
            self.logger.warning("No provider selected. Cannot add model.")
            return
            
        if new_model and new_model not in self.staged_model_lists[provider_id]:
            self.logger.info(f"Staging new model '{new_model}' for provider '{provider_id}'")
            self.staged_model_lists[provider_id].append(new_model)
            self._update_model_ui(provider_id) # Rebuild UI to reflect change
            self.new_model_entry.delete(0, "end")
        else:
            self.logger.warning(f"Model '{new_model}' is empty or already exists.")

    # --- NEW: Removes a model from the staged list and UI ---
    def _remove_model_from_ui(self, provider_id: str, model_name: str):
        if model_name in self.staged_model_lists[provider_id]:
            self.logger.info(f"Unstaging model '{model_name}' for provider '{provider_id}'")
            self.staged_model_lists[provider_id].remove(model_name)
            self._update_model_ui(provider_id) # Rebuild UI
        else:
            self.logger.warning(f"Could not find model '{model_name}' to remove.")

    # --- (Unchanged) ---
    def create_api_keys_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(tab, text="Gemini API Key:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.gemini_key_entry = ctk.CTkEntry(tab, show="*", placeholder_text="Set as GEMINI_API_KEY env var")
        self.gemini_key_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(tab, text="Test", command=lambda: self.test_connection("gemini")).grid(row=0, column=2, padx=10, pady=10)
        
        ctk.CTkLabel(tab, text="OpenRouter API Key:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.openrouter_key_entry = ctk.CTkEntry(tab, show="*", placeholder_text="Set as OPENROUTER_API_KEY env var")
        self.openrouter_key_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(tab, text="Test", command=lambda: self.test_connection("openrouter")).grid(row=1, column=2, padx=10, pady=10)

        ctk.CTkLabel(tab, text="Ollama Base URL:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.ollama_url_entry = ctk.CTkEntry(tab)
        self.ollama_url_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(tab, text="Test", command=lambda: self.test_connection("ollama")).grid(row=2, column=2, padx=10, pady=10)

    # --- (Unchanged) ---
    def create_hotkeys_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(tab, text="Open Chat:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.hotkey_chat_entry = ctk.CTkEntry(tab)
        self.hotkey_chat_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        ctk.CTkLabel(tab, text="Screen Capture:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.hotkey_screen_entry = ctk.CTkEntry(tab)
        self.hotkey_screen_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

    # --- (Unchanged) ---
    def create_plugins_tab(self, tab):
        ctk.CTkLabel(tab, text="Plugin management (coming soon)").pack(padx=20, pady=20)
        
    # --- HEAVILY MODIFIED (Merged with a3) ---
    def load_settings(self):
        """Loads all settings from config files into the UI fields."""
        
        # --- Load UI Config (from a3) ---
        ui_config = self.config.get_config("ui_config.json")
        self.theme_var.set(ui_config.get("theme", "System"))
        
        # --- Restore window geometry (from a3) ---
        geometry = ui_config.get("settings_window", {}).get("geometry")
        if geometry:
            self.logger.debug(f"Restoring settings window geometry: {geometry}")
            self.geometry(geometry)
        
        # --- Load Models Config ---
        models_config = self.config.get_config("models_config.json")
        
        # 1. Load providers and their model lists into the staging variable
        providers_data = models_config.get("providers", {})
        self.staged_model_lists = {p: d.get("models", []) for p, d in providers_data.items()}
        
        # 2. Get provider IDs and configure the dropdown
        provider_ids = list(self.staged_model_lists.keys())
        self.provider_dropdown.configure(values=provider_ids)
        
        # 3. Get the saved active provider and model
        active_provider = models_config.get("active_provider")
        active_model = models_config.get("active_model")

        # 4. Set the provider dropdown. This will trigger _on_provider_changed()
        if active_provider and active_provider in provider_ids:
            self.provider_var.set(active_provider)
            self._update_model_ui(active_provider) # Manually update UI for first load
        elif provider_ids:
            self.provider_var.set(provider_ids[0])
            self._update_model_ui(provider_ids[0])

        # 5. Set the active model dropdown
        current_provider_models = self.staged_model_lists.get(self.provider_var.get(), [])
        if active_model and active_model in current_provider_models:
            self.model_var.set(active_model)
        elif current_provider_models:
            self.model_var.set(current_provider_models[0])
            
        # --- Load API Keys Config ---
        self.gemini_key_entry.delete(0, "end")
        self.gemini_key_entry.insert(0, models_config.get("providers", {}).get("gemini", {}).get("api_key", ""))
        self.openrouter_key_entry.delete(0, "end")
        self.openrouter_key_entry.insert(0, models_config.get("providers", {}).get("openrouter", {}).get("api_key", ""))
        self.ollama_url_entry.delete(0, "end")
        self.ollama_url_entry.insert(0, models_config.get("providers", {}).get("ollama", {}).get("base_url", "http://localhost:11434"))
        
        # --- Load System Config ---
        system_config = self.config.get_config("system_config.json")
        self.hotkey_chat_entry.delete(0, "end")
        self.hotkey_chat_entry.insert(0, system_config.get("hotkeys", {}).get("open_chat", "<ctrl>+<shift>+<space>"))
        self.hotkey_screen_entry.delete(0, "end")
        self.hotkey_screen_entry.insert(0, system_config.get("hotkeys", {}).get("screen_capture", "<ctrl>+<shift>+x"))

    # --- HEAVILY MODIFIED (Merged with a3) ---
    def save_settings(self):
        """Saves all settings from the UI fields back to config files."""
        self.logger.info("Saving settings...")
        
        # --- Save UI Config (from a3) ---
        ui_config = self.config.get_config("ui_config.json")
        ui_config["theme"] = self.theme_var.get()
        # --- Save window geometry (from a3) ---
        ui_config.setdefault("settings_window", {})["geometry"] = self.geometry()
        self.config.save_config("ui_config.json", ui_config)
        
        # --- Apply theme immediately (from a3) ---
        ctk.set_appearance_mode(self.theme_var.get().lower())
        
        # --- Save Models Config ---
        models_config = self.config.get_config("models_config.json")
        
        # 1. Save active provider and model
        models_config["active_provider"] = self.provider_var.get()
        models_config["active_model"] = self.model_var.get()
        
        # 2. Save API keys and URLs
        models_config["providers"]["gemini"]["api_key"] = self.gemini_key_entry.get()
        models_config["providers"]["openrouter"]["api_key"] = self.openrouter_key_entry.get()
        models_config["providers"]["ollama"]["base_url"] = self.ollama_url_entry.get()
        
        # 3. Save the edited model lists from our staging variable
        for provider_id, models_list in self.staged_model_lists.items():
            if provider_id in models_config["providers"]:
                models_config["providers"][provider_id]["models"] = models_list
            else:
                # This would happen if a provider was removed, but we don't support that
                pass
                
        self.config.save_config("models_config.json", models_config)
        
        # --- Save System Config ---
        system_config = self.config.get_config("system_config.json")
        system_config["hotkeys"]["open_chat"] = self.hotkey_chat_entry.get()
        system_config["hotkeys"]["screen_capture"] = self.hotkey_screen_entry.get()
        self.config.save_config("system_config.json", system_config)

        # Publish an event so other services (like HotkeyManager) can reload
        self.publish_async_event("UI_EVENT.SETTINGS_CHANGED")
        self.hide()

    # --- NEW: Window position saving (from a3) ---
    def _on_window_move(self, event):
        """Debounce method to save window geometry on move/resize."""
        # This event fires rapidly. We save the *latest* geometry
        # string. It will be properly saved only when 'hide' or 'save' is called.
        self.last_geometry = self.geometry()

    # --- (Unchanged) ---
    def test_connection(self, provider: str):
        self.logger.info(f"Requesting connection test for: {provider}")
        self.publish_async_event(f"API_EVENT.TEST_CONNECTION", provider=provider)
        
    # --- MODIFIED: Using simpler version from a3 ---
    def publish_async_event(self, event_type: str, *args, **kwargs):
        app = self.locator.resolve("app")
        async_loop = getattr(app, "async_loop", None)
        if not async_loop:
            self.logger.warning("Async loop not available. Cannot publish event.")
            return
        coro = self.events.publish(event_type, *args, **kwargs)
        asyncio.run_coroutine_threadsafe(coro, async_loop)

    def show(self):
        self.load_settings() # Load fresh data each time
        self.deiconify()
        self.lift()
        self.focus_force()
        self.is_visible = True
        
    # --- MODIFIED: Merged with a3 to save geometry ---
    def hide(self):
        # --- NEW: Save geometry on hide (from a3) ---
        if self.last_geometry:
            ui_config = self.config.get_config("ui_config.json")
            ui_config.setdefault("settings_window", {})["geometry"] = self.last_geometry
            self.config.save_config("ui_config.json", ui_config)
            self.last_geometry = ""
            
        self.withdraw()
        self.is_visible = False