# file: ui/settings_window.py

import logging
import asyncio
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from core.service_locator import locator
from core.event_dispatcher import EventDispatcher
from utils.config_loader import ConfigLoader

class SettingsWindow(ctk.CTkToplevel):
    """
    The main settings window, now with sidebar navigation.
    """
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.locator = locator
        self.events: EventDispatcher = self.locator.resolve("event_dispatcher")
        self.config: ConfigLoader = self.locator.resolve("config_loader")
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.title("Settings")
        self.geometry("1050x480") # 1.75x width
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1) # Main content area expands

        # --- Staging for model list edits ---
        self.staged_model_lists = {}

        # --- StringVars for UI elements ---
        self.active_model_var = ctk.StringVar() # Combined: "provider/model"
        self.manage_provider_var = ctk.StringVar() # For the "Manage Models" section
        self.theme_var = ctk.StringVar()
        
        # --- NEW: StringVars for API Key test models ---
        self.gemini_test_model_var = ctk.StringVar()
        self.openrouter_test_model_var = ctk.StringVar()
        self.ollama_test_model_var = ctk.StringVar()
        
        # --- NEW: StringVars for plugin settings ---
        self.plugin_screencapture_enabled_var = ctk.StringVar(value="on")

        # --- Unsaved Changes Flag ---
        self.has_unsaved_changes = False
        
        # --- NEW: Flag to prevent dirty marking during load (#2) ---
        self.is_loading_settings = False

        # --- Sidebar Navigation ---
        self.sidebar = ctk.CTkFrame(self, width=150)
        self.sidebar.grid(row=0, column=0, sticky="nsw", padx=(10, 0), pady=10)
        self.sidebar.grid_propagate(False)

        # --- Content Frame ---
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        self.nav_buttons = {}
        self.content_frames = {}

        # --- Add navigation items ---
        self._add_nav_item("General", self.create_general_tab)
        self._add_nav_item("Models", self.create_models_tab)
        self._add_nav_item("API Keys", self.create_api_keys_tab)
        self._add_nav_item("Hotkeys", self.create_hotkeys_tab)
        # --- MODIFIED: Enabled Plugins tab ---
        self._add_nav_item("Plugins", self.create_plugins_tab) 
        self._add_nav_item("MCP Servers", self.create_coming_soon_tab, is_disabled=True)
        
        # --- Save/Close Buttons ---
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="e")
        
        self.save_button = ctk.CTkButton(self.button_frame, text="Save", command=self.save_settings)
        self.save_button.pack(side="left", padx=5)
        self.save_button.configure(state="disabled")
        
        self.close_button = ctk.CTkButton(self.button_frame, text="Close", command=self.hide)
        self.close_button.pack(side="left", padx=5)

        self.withdraw() # Hide at start
        self.protocol("WM_DELETE_WINDOW", self.hide)
        self.is_visible = False
        
        # --- Trace provider changes ---
        self.manage_provider_var.trace_add("write", self._on_manage_provider_changed)
        
        # --- Subscribe to connection test results ---
        self.events.subscribe("API_EVENT.TEST_CONNECTION_RESULT", self.on_connection_test_result)
        
        # Show the first frame
        self._show_content_frame("General")

    # --- CHANGED: Sidebar Navigation Methods (#1) ---
    def _add_nav_item(self, name: str, creation_func, is_disabled=False):
        """Adds a button to the sidebar and creates its corresponding content frame."""
        frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        # --- FIX: Removed frame.grid() call. Frame should not be shown on creation. (#1) ---
        creation_func(frame) # Populate the frame
        self.content_frames[name] = frame
        
        default_text_color = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
        if is_disabled:
            default_text_color = ctk.ThemeManager.theme["CTkButton"]["text_color_disabled"]

        button = ctk.CTkButton(
            self.sidebar, 
            text=name, 
            command=lambda n=name: self._show_content_frame(n),
            fg_color="transparent",
            anchor="w",
            text_color=default_text_color
        )
        button.pack(fill="x", padx=10, pady=5)
        
        if is_disabled:
            button.configure(state="disabled")

        self.nav_buttons[name] = button

    def _show_content_frame(self, name: str):
        """Hides all content frames and shows the one specified by name."""
        active_color = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        default_text_color = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
        active_text_color = ctk.ThemeManager.theme["CTkButton"]["text_color"]

        for frame_name, frame in self.content_frames.items():
            button = self.nav_buttons[frame_name]
            
            if button.cget("state") == "disabled":
                continue

            if frame_name == name:
                # --- This is where the frame is correctly shown ---
                frame.grid(row=0, column=0, sticky="nsew") 
                button.configure(
                    fg_color=active_color,
                    text_color=active_text_color
                )
            else:
                # --- And correctly hidden here ---
                frame.grid_forget() 
                button.configure(
                    fg_color="transparent",
                    text_color=default_text_color
                )

    # --- Placeholder tab for disabled items ---
    def create_coming_soon_tab(self, parent_frame):
        parent_frame.grid_rowconfigure(0, weight=1)
        parent_frame.grid_columnconfigure(0, weight=1)
        
        label_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        label_frame.grid(row=0, column=0, sticky="nsew")
        
        label_frame.grid_rowconfigure(0, weight=1)
        label_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            label_frame, 
            text="Coming Soon",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=ctk.ThemeManager.theme["CTkButton"]["text_color_disabled"]
        ).grid(row=0, column=0, sticky="nsew")

    # --- CHANGED: Unsaved Changes Method (#2) ---
    def _mark_dirty(self, *args):
        """Flags that changes have been made and enables the Save button."""
        
        # --- FIX: Don't mark as dirty if we're just loading settings (#2) ---
        if self.is_loading_settings:
            return 
            
        if not self.has_unsaved_changes:
            self.has_unsaved_changes = True
            self.save_button.configure(state="normal")

    # --- General Tab ---
    def create_general_tab(self, parent_frame):
        parent_frame.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(parent_frame, text="Theme:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        theme_menu = ctk.CTkOptionMenu(parent_frame, variable=self.theme_var, values=["System", "Dark", "Light"])
        theme_menu.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        
        self.theme_var.trace_add("write", self._mark_dirty)

    # --- Models Tab ---
    def create_models_tab(self, parent_frame):
        parent_frame.grid_columnconfigure(1, weight=1)

        # --- MODIFIED: Row 0 - Manage Provider (Moved up) ---
        ctk.CTkLabel(parent_frame, text="Manage Provider:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.manage_provider_dropdown = ctk.CTkOptionMenu(parent_frame, variable=self.manage_provider_var)
        self.manage_provider_dropdown.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # --- MODIFIED: Row 1 - Active Model (Moved down) ---
        ctk.CTkLabel(parent_frame, text="Active Model:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.model_dropdown = ctk.CTkOptionMenu(parent_frame, variable=self.active_model_var, values=[])
        self.model_dropdown.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        self.active_model_var.trace_add("write", self._mark_dirty)

        # --- MODIFIED: Row 2 & 3 - Separator ---
        ctk.CTkLabel(parent_frame, text="Manage Models", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, columnspan=2, padx=10, pady=(10,0), sticky="w")
        ctk.CTkFrame(parent_frame, height=2).grid(row=3, column=0, columnspan=2, padx=10, pady=(5,10), sticky="ew")

        # --- MODIFIED: Row 4 - Model List ---
        self.model_list_frame = ctk.CTkScrollableFrame(parent_frame)
        self.model_list_frame.grid(row=4, column=0, columnspan=2, padx=10, pady=0, sticky="nsew")
        parent_frame.grid_rowconfigure(4, weight=1)

        # --- MODIFIED: Row 5 - Add Model Frame ---
        add_frame = ctk.CTkFrame(parent_frame)
        add_frame.grid(row=5, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        add_frame.grid_columnconfigure(0, weight=1)

        self.new_model_entry = ctk.CTkEntry(add_frame, placeholder_text="Enter model name (e.g., llama3-8b)")
        self.new_model_entry.grid(row=0, column=0, padx=(0, 5), pady=0, sticky="ew")
        self.new_model_entry.bind("<Return>", self._add_model_to_ui)

        self.add_model_button = ctk.CTkButton(add_frame, text="Add Model", width=100, command=self._add_model_to_ui)
        self.add_model_button.grid(row=0, column=1, padx=(5, 0), pady=0)

    # --- MODIFIED: This function now updates both UI lists ---
    def _on_manage_provider_changed(self, *args):
        provider_id = self.manage_provider_var.get()
        if provider_id:
            self._update_model_ui(provider_id)
            self._update_active_model_dropdown(provider_id) # <-- ADDED

    # --- NEW: Helper function to filter the Active Model dropdown ---
    def _update_active_model_dropdown(self, provider_id: str):
        """Updates the 'Active Model' dropdown to show only models for the selected provider."""
        self.logger.debug(f"Updating active model dropdown for provider: {provider_id}")
        
        models_list = self.staged_model_lists.get(provider_id, [])
        formatted_models = [f"{provider_id}/{model}" for model in models_list]
        
        current_active_model = self.active_model_var.get()
        
        # Configure the dropdown with the new list of models
        self.model_dropdown.configure(values=formatted_models)
        
        if current_active_model in formatted_models:
            # The current selection is valid for this provider, just ensure it's set
            self.model_dropdown.set(current_active_model)
        elif formatted_models:
            # The current selection is invalid, set to the first model in the new list
            self.active_model_var.set(formatted_models[0]) # This will trigger its own trace
        else:
            # No models for this provider
            self.active_model_var.set("")
            self.model_dropdown.set("") # Clear visual

    def _update_model_ui(self, provider_id: str):
        self.logger.debug(f"Updating model management UI for provider: {provider_id}")
        
        models_list = self.staged_model_lists.get(provider_id, [])
        
        for widget in self.model_list_frame.winfo_children():
            widget.destroy()
            
        for model_name in models_list:
            frame = ctk.CTkFrame(self.model_list_frame)
            frame.pack(fill="x", expand=True, padx=5, pady=2)
            frame.grid_columnconfigure(0, weight=1)

            label = ctk.CTkLabel(frame, text=model_name)
            label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

            menu_button = ctk.CTkButton(
                frame, 
                text="⋮", 
                width=30, 
            )
            menu_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")
            menu_button.configure(command=lambda p=provider_id, m=model_name, w=menu_button: self._show_model_menu(p, m, w))

    # --- MODIFIED: Also updates the active model dropdown ---
    def _add_model_to_ui(self, event=None):
        provider_id = self.manage_provider_var.get()
        new_model = self.new_model_entry.get().strip()
        
        if not provider_id:
            self.logger.warning("No provider selected. Cannot add model.")
            return
            
        if new_model and new_model not in self.staged_model_lists[provider_id]:
            self.logger.info(f"Staging new model '{new_model}' for provider '{provider_id}'")
            self.staged_model_lists[provider_id].append(new_model)
            self._update_model_ui(provider_id)
            self._update_active_model_dropdown(provider_id)
            self._update_test_model_dropdowns() # <-- NEW
            self.new_model_entry.delete(0, "end")
            self._mark_dirty() 
        else:
            self.logger.warning(f"Model '{new_model}' is empty or already exists.")

    # --- MODIFIED: Also updates the active model dropdown ---
    def _remove_model_from_ui(self, provider_id: str, model_name: str):
        if model_name in self.staged_model_lists[provider_id]:
            self.logger.info(f"Unstaging model '{model_name}' for provider '{provider_id}'")
            self.staged_model_lists[provider_id].remove(model_name)
            self._update_model_ui(provider_id)
            self._update_active_model_dropdown(provider_id)
            self._update_test_model_dropdowns() # <-- NEW
            self._mark_dirty()
        else:
            self.logger.warning(f"Could not find model '{model_name}' to remove.")

    # --- Model Context Menu Methods ---
    def _show_model_menu(self, provider_id: str, model_name: str, widget: ctk.CTkButton):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Remove", 
            command=lambda: self._remove_model_from_ui(provider_id, model_name)
        )
        menu.add_command(
            label="Set as Default", 
            command=lambda: self._set_model_as_default(provider_id, model_name)
        )
        menu.add_command(
            label="Test Model", 
            command=lambda: self._test_model(provider_id, model_name)
        )
        menu.post(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())

    def _set_model_as_default(self, provider_id: str, model_name: str):
        formatted_model = f"{provider_id}/{model_name}"
        if formatted_model in self._get_all_models_formatted():
            self.active_model_var.set(formatted_model)
            self.logger.info(f"Set active model to: {formatted_model}")
            self._mark_dirty()
        else:
            self.logger.warning(f"Could not set default model: '{formatted_model}' not found.")

    def _test_model(self, provider_id: str, model_name: str):
        self.logger.info(f"Requesting test for model: {provider_id}/{model_name}")
        self.publish_async_event(
            "API_EVENT.TEST_MODEL", 
            provider=provider_id, 
            model=model_name,
            timeout=5
        )

    # --- API Keys Tab ---
    def create_api_keys_tab(self, parent_frame):
        # --- MODIFIED: Added column 2, col 1 still stretches ---
        parent_frame.grid_columnconfigure(1, weight=1)
        
        # --- Gemini ---
        ctk.CTkLabel(parent_frame, text="Gemini API Key:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.gemini_key_entry = ctk.CTkEntry(parent_frame, show="*", placeholder_text="Set as GEMINI_API_KEY env var")
        self.gemini_key_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        # --- NEW: Gemini model dropdown ---
        self.gemini_model_menu = ctk.CTkOptionMenu(parent_frame, variable=self.gemini_test_model_var, values=[])
        self.gemini_model_menu.grid(row=0, column=2, padx=(0, 5), pady=10)
        self.gemini_model_menu.set("") # Clear visual
        
        # --- MODIFIED: Column changed from 2 to 3 ---
        ctk.CTkButton(parent_frame, text="Test", command=lambda: self.test_connection("gemini")).grid(row=0, column=3, padx=(5, 10), pady=10)
        
        # --- MODIFIED: Column changed from 3 to 4 ---
        self.gemini_status = ctk.CTkLabel(parent_frame, text="●", text_color="gray", font=ctk.CTkFont(size=20))
        self.gemini_status.grid(row=0, column=4, padx=5, pady=10)
        
        # --- OpenRouter ---
        ctk.CTkLabel(parent_frame, text="OpenRouter API Key:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.openrouter_key_entry = ctk.CTkEntry(parent_frame, show="*", placeholder_text="Set as OPENROUTER_API_KEY env var")
        self.openrouter_key_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        # --- NEW: OpenRouter model dropdown ---
        self.openrouter_model_menu = ctk.CTkOptionMenu(parent_frame, variable=self.openrouter_test_model_var, values=[])
        self.openrouter_model_menu.grid(row=1, column=2, padx=(0, 5), pady=10)
        self.openrouter_model_menu.set("") # Clear visual

        # --- MODIFIED: Column changed from 2 to 3 ---
        ctk.CTkButton(parent_frame, text="Test", command=lambda: self.test_connection("openrouter")).grid(row=1, column=3, padx=(5, 10), pady=10)
        
        # --- MODIFIED: Column changed from 3 to 4 ---
        self.openrouter_status = ctk.CTkLabel(parent_frame, text="●", text_color="gray", font=ctk.CTkFont(size=20))
        self.openrouter_status.grid(row=1, column=4, padx=5, pady=10)

        # --- Ollama ---
        ctk.CTkLabel(parent_frame, text="Ollama Base URL:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.ollama_url_entry = ctk.CTkEntry(parent_frame)
        self.ollama_url_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        # --- NEW: Ollama model dropdown ---
        self.ollama_model_menu = ctk.CTkOptionMenu(parent_frame, variable=self.ollama_test_model_var, values=[])
        self.ollama_model_menu.grid(row=2, column=2, padx=(0, 5), pady=10)
        self.ollama_model_menu.set("") # Clear visual

        # --- MODIFIED: Column changed from 2 to 3 ---
        ctk.CTkButton(parent_frame, text="Test", command=lambda: self.test_connection("ollama")).grid(row=2, column=3, padx=(5, 10), pady=10)
        
        # --- MODIFIED: Column changed from 3 to 4 ---
        self.ollama_status = ctk.CTkLabel(parent_frame, text="●", text_color="gray", font=ctk.CTkFont(size=20))
        self.ollama_status.grid(row=2, column=4, padx=5, pady=10)

        self.gemini_key_entry.bind("<KeyRelease>", self._mark_dirty)
        self.openrouter_key_entry.bind("<KeyRelease>", self._mark_dirty)
        self.ollama_url_entry.bind("<KeyRelease>", self._mark_dirty)

    # --- NEW: Helper to update test dropdowns ---
    def _update_test_model_dropdowns(self):
        """Populates the model dropdowns on the API Keys tab."""
        self.logger.debug("Updating API Key test model dropdowns.")
        
        # --- Gemini ---
        gemini_models = self.staged_model_lists.get("gemini", [])
        self.gemini_model_menu.configure(values=gemini_models)
        current_gemini = self.gemini_test_model_var.get()
        if current_gemini in gemini_models:
            self.gemini_model_menu.set(current_gemini) # Keep selection if valid
        elif gemini_models:
            self.gemini_test_model_var.set(gemini_models[0])
        else:
            self.gemini_test_model_var.set("")
            self.gemini_model_menu.set("") # Clear visual

        # --- OpenRouter ---
        openrouter_models = self.staged_model_lists.get("openrouter", [])
        self.openrouter_model_menu.configure(values=openrouter_models)
        current_openrouter = self.openrouter_test_model_var.get()
        if current_openrouter in openrouter_models:
            self.openrouter_model_menu.set(current_openrouter)
        elif openrouter_models:
            self.openrouter_test_model_var.set(openrouter_models[0])
        else:
            self.openrouter_test_model_var.set("")
            self.openrouter_model_menu.set("")

        # --- Ollama ---
        ollama_models = self.staged_model_lists.get("ollama", [])
        self.ollama_model_menu.configure(values=ollama_models)
        current_ollama = self.ollama_test_model_var.get()
        if current_ollama in ollama_models:
            self.ollama_model_menu.set(current_ollama)
        elif ollama_models:
            self.ollama_test_model_var.set(ollama_models[0])
        else:
            self.ollama_test_model_var.set("")
            self.ollama_model_menu.set("")

    # --- Connection Status Methods ---
    def on_connection_test_result(self, provider: str, success: bool):
        self.logger.debug(f"Received connection test result: {provider} -> {success}")
        self.after(0, self.update_status, provider, success)

    def update_status(self, provider: str, success: bool | None | str):
        if success is None:
            color = "gray"
        elif success == "testing":
            color = "orange"
        else:
            color = "green" if success else "red"
        
        if provider == "gemini":
            self.gemini_status.configure(text_color=color)
        elif provider == "openrouter":
            self.openrouter_status.configure(text_color=color)
        elif provider == "ollama":
            self.ollama_status.configure(text_color=color)

    # --- Hotkeys Tab ---
    def create_hotkeys_tab(self, parent_frame):
        parent_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(parent_frame, text="Open Chat:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.hotkey_chat_entry = ctk.CTkEntry(parent_frame)
        self.hotkey_chat_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(parent_frame, text="Screen Capture:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.hotkey_screen_entry = ctk.CTkEntry(parent_frame)
        self.hotkey_screen_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        self.hotkey_chat_entry.bind("<KeyRelease>", self._mark_dirty)
        self.hotkey_screen_entry.bind("<KeyRelease>", self._mark_dirty)
        
    # --- NEW: Plugins Tab ---
    def create_plugins_tab(self, parent_frame):
        parent_frame.grid_columnconfigure(1, weight=1)
        
        # --- Screen Capture Plugin ---
        ctk.CTkLabel(parent_frame, text="Screen Capture Plugin", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.plugin_screencapture_checkbox = ctk.CTkCheckBox(
            parent_frame,
            text="Enable Plugin (Hotkeys will be disabled if unchecked)",
            variable=self.plugin_screencapture_enabled_var,
            onvalue="on",
            offvalue="off"
        )
        self.plugin_screencapture_checkbox.grid(row=1, column=0, columnspan=2, padx=15, pady=5, sticky="w")
        
        self.plugin_screencapture_enabled_var.trace_add("write", self._mark_dirty)

    # --- Helper to get combined model list ---
    def _get_all_models_formatted(self) -> list[str]:
        formatted_list = []
        for provider, models_list in self.staged_model_lists.items():
            for model in models_list:
                formatted_list.append(f"{provider}/{model}")
        return formatted_list

    # --- CHANGED: Load/Save (#2) ---
    def load_settings(self):
        """Loads all settings from config files into the UI fields."""
        
        # --- FIX: Set loading flag to TRUE (#2) ---
        self.is_loading_settings = True
        
        self.has_unsaved_changes = False
        self.save_button.configure(state="disabled")

        # --- Load UI Config ---
        ui_config = self.config.get_config("ui_config.json")
        self.theme_var.set(ui_config.get("theme", "System")) # Triggers trace, but _mark_dirty will now return
        
        geometry = ui_config.get("settings_window", {}).get("geometry")
        if geometry:
            self.logger.debug(f"Restoring settings window geometry: {geometry}")
            self.geometry(geometry)
        
        # --- Load Models Config ---
        models_config = self.config.get_config("models_config.json")
        
        providers_data = models_config.get("providers", {})
        self.staged_model_lists = {p: d.get("models", []) for p, d in providers_data.items()}
        
        # --- NEW: Populate API key test dropdowns ---
        self._update_test_model_dropdowns()
        
        provider_ids = list(self.staged_model_lists.keys())
        self.manage_provider_dropdown.configure(values=provider_ids)
        
        active_provider = models_config.get("active_provider")
        active_model = models_config.get("active_model")

        # --- MODIFIED: Set active_model_var *before* provider_var ---
        # This ensures the trace on provider_var can respect the loaded active model.
        formatted_active_model = f"{active_provider}/{active_model}"
        all_models_formatted = self._get_all_models_formatted() # Used for validation

        if active_model and formatted_active_model in all_models_formatted:
            self.active_model_var.set(formatted_active_model)
        elif all_models_formatted:
            # Fallback to the first available model if saved one is invalid
            self.active_model_var.set(all_models_formatted[0]) 
            active_provider, _ = all_models_formatted[0].split("/", 1) # Update active provider
        else:
            self.active_model_var.set("")
            
        # --- MODIFIED: Set manage_provider_var *second* ---
        # This triggers the _on_manage_provider_changed trace, which will
        # now call _update_model_ui AND _update_active_model_dropdown.
        if active_provider and active_provider in provider_ids:
            self.manage_provider_var.set(active_provider)
        elif provider_ids:
            self.manage_provider_var.set(provider_ids[0])
        else:
            self.manage_provider_var.set("") # No providers

        # --- REMOVED: Redundant dropdown configuration ---
        # The trace triggered by manage_provider_var.set() now handles
        # populating and setting the active_model_dropdown.
            
        # --- Load API Keys Config ---
        # .insert() does not trigger <KeyRelease>, so these are safe
        self.gemini_key_entry.delete(0, "end")
        self.gemini_key_entry.insert(0, models_config.get("providers", {}).get("gemini", {}).get("api_key", ""))
        self.openrouter_key_entry.delete(0, "end")
        self.openrouter_key_entry.insert(0, models_config.get("providers", {}).get("openrouter", {}).get("api_key", ""))
        self.ollama_url_entry.delete(0, "end")
        self.ollama_url_entry.insert(0, models_config.get("providers", {}).get("ollama", {}).get("base_url", "http://localhost:11434"))
        
        self.update_status("gemini", None)
        self.update_status("openrouter", None)
        self.update_status("ollama", None)

        # --- Load System Config ---
        system_config = self.config.get_config("system_config.json")
        self.hotkey_chat_entry.delete(0, "end")
        self.hotkey_chat_entry.insert(0, system_config.get("hotkeys", {}).get("open_chat", "<ctrl>+<shift>+<space>"))
        self.hotkey_screen_entry.delete(0, "end")
        self.hotkey_screen_entry.insert(0, system_config.get("hotkeys", {}).get("screen_capture", "<ctrl>+<shift>+x"))

        # --- NEW: Load Plugin Config ---
        plugin_config = system_config.get("plugins", {}).get("ScreenCapture", {})
        plugin_enabled = plugin_config.get("enabled", True) # Default to True if not specified
        self.plugin_screencapture_enabled_var.set("on" if plugin_enabled else "off")

        # --- FIX: Set loading flag to FALSE (#2) ---
        self.is_loading_settings = False

    def save_settings(self):
        """Saves all settings from the UI fields back to config files."""
        self.logger.info("Saving settings...")
        
        # --- Save UI Config ---
        ui_config = self.config.get_config("ui_config.json")
        ui_config["theme"] = self.theme_var.get()
        self._save_geometry()
        self.config.save_config("ui_config.json", ui_config)
        
        ctk.set_appearance_mode(self.theme_var.get().lower())
        
        # --- Save Models Config ---
        models_config = self.config.get_config("models_config.json")
        
        active_model_str = self.active_model_var.get()
        if "/" in active_model_str:
            provider, model = active_model_str.split("/", 1)
            models_config["active_provider"] = provider
            models_config["active_model"] = model
        else:
            # Handle case where no model is selected
            models_config["active_provider"] = self.manage_provider_var.get()
            models_config["active_model"] = ""
        
        models_config["providers"]["gemini"]["api_key"] = self.gemini_key_entry.get()
        models_config["providers"]["openrouter"]["api_key"] = self.openrouter_key_entry.get()
        models_config["providers"]["ollama"]["base_url"] = self.ollama_url_entry.get()
        
        for provider_id, models_list in self.staged_model_lists.items():
            if provider_id in models_config["providers"]:
                models_config["providers"][provider_id]["models"] = models_list
            
        self.config.save_config("models_config.json", models_config)
        
        # --- Save System Config ---
        system_config = self.config.get_config("system_config.json")
        system_config["hotkeys"]["open_chat"] = self.hotkey_chat_entry.get()
        system_config["hotkeys"]["screen_capture"] = self.hotkey_screen_entry.get()
        # --- NEW: Save Plugin Config ---
        system_config.setdefault("plugins", {}).setdefault("ScreenCapture", {})
        system_config["plugins"]["ScreenCapture"]["enabled"] = (self.plugin_screencapture_enabled_var.get() == "on")
        
        self.config.save_config("system_config.json", system_config)

        self.publish_async_event("UI_EVENT.SETTINGS_CHANGED")
        
        self.has_unsaved_changes = False
        self.save_button.configure(state="disabled")
        
        self.hide(force=True)

    # --- Window State Management ---
    def _save_geometry(self):
        ui_config = self.config.get_config("ui_config.json")
        ui_config.setdefault("settings_window", {})["geometry"] = self.geometry()
        self.config.save_config("ui_config.json", ui_config)

    # --- MODIFIED: Now sends the selected model ---
    def test_connection(self, provider: str):
        self.logger.info(f"Requesting connection test for: {provider}")
        
        self.update_status(provider, "testing")

        key_or_url = ""
        model_name = ""
        
        if provider == "gemini": 
            key_or_url = self.gemini_key_entry.get()
            model_name = self.gemini_test_model_var.get()
        elif provider == "openrouter": 
            key_or_url = self.openrouter_key_entry.get()
            model_name = self.openrouter_test_model_var.get()
        elif provider == "ollama": 
            key_or_url = self.ollama_url_entry.get()
            model_name = self.ollama_test_model_var.get()

        # --- NEW: Check if a model was selected ---
        if not model_name:
            self.logger.warning(f"No model selected for {provider} test.")
            messagebox.showwarning("Test Failed", f"Please select a model for {provider} to test.")
            self.update_status(provider, False) # Set to failed
            return

        self.publish_async_event(
            f"API_EVENT.TEST_CONNECTION", 
            provider=provider, 
            value=key_or_url,
            model=model_name, # <-- NEWLY ADDED
            timeout=5
        )
        
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
        
    def hide(self, force: bool = False):
        if self.has_unsaved_changes and not force:
            if not messagebox.askyesno("Unsaved Changes", 
                                    "You have unsaved changes. Are you sure you want to close without saving?"):
                return
        
        self._save_geometry()
        
        # Reset flags
        self.has_unsaved_changes = False
        self.save_button.configure(state="disabled")
            
        self.withdraw()
        self.is_visible = False