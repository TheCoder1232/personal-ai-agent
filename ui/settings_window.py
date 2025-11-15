# file: ui/settings_window.py

import logging
import asyncio
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from core.service_locator import locator
from core.event_dispatcher import EventDispatcher
from utils.config_loader import ConfigLoader
from .settings_tabs.general_tab import GeneralTab
from .settings_tabs.models_tab import ModelsTab
from .settings_tabs.api_keys_tab import ApiKeysTab
from .settings_tabs.hotkeys_tab import HotkeysTab
from .settings_tabs.plugins_tab import PluginsTab
from .settings_tabs.coming_soon_tab import ComingSoonTab

class SettingsWindow(ctk.CTkToplevel):
    """
    The main settings window, now acting as a container for modular tabs.
    """
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.locator = locator
        self.events: EventDispatcher = self.locator.resolve("event_dispatcher")
        self.config: ConfigLoader = self.locator.resolve("config_loader")
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.title("Settings")
        self.geometry("1050x480")
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._init_vars()
        self._setup_ui()
        
        self.withdraw()
        self.protocol("WM_DELETE_WINDOW", self.hide)
        self.is_visible = False
        
        self.events.subscribe("API_EVENT.TEST_CONNECTION_RESULT", self.on_connection_test_result)
        self.events.subscribe("SETTINGS_EVENT.MODEL_LIST_CHANGED", self._on_model_list_changed)

        self._show_content_frame("General")

    def _init_vars(self):
        """Initialize all tk variables."""
        self.staged_model_lists = {}
        self.active_model_var = ctk.StringVar()
        self.manage_provider_var = ctk.StringVar()
        self.theme_var = ctk.StringVar()
        self.gemini_test_model_var = ctk.StringVar()
        self.openrouter_test_model_var = ctk.StringVar()
        self.ollama_test_model_var = ctk.StringVar()
        self.plugin_screencapture_enabled_var = ctk.StringVar(value="on")
        self.has_unsaved_changes = False
        self.is_loading_settings = False

    def _setup_ui(self):
        """Setup main UI layout and buttons."""
        self.sidebar = ctk.CTkFrame(self, width=150)
        self.sidebar.grid(row=0, column=0, sticky="nsw", padx=(10, 0), pady=10)
        self.sidebar.grid_propagate(False)

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        self.nav_buttons = {}
        self.content_frames = {}
        
        self._create_all_tabs()

        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="e")
        
        self.save_button = ctk.CTkButton(self.button_frame, text="Save", command=self.save_settings, state="disabled")
        self.save_button.pack(side="left", padx=5)
        
        self.close_button = ctk.CTkButton(self.button_frame, text="Close", command=self.hide)
        self.close_button.pack(side="left", padx=5)

    def _create_all_tabs(self):
        """Instantiate and add all setting tabs."""
        self._add_nav_item("General", self._create_general_tab)
        self._add_nav_item("Models", self._create_models_tab)
        self._add_nav_item("API Keys", self._create_api_keys_tab)
        self._add_nav_item("Hotkeys", self._create_hotkeys_tab)
        self._add_nav_item("Plugins", self._create_plugins_tab)
        self._add_nav_item("MCP Servers", lambda parent: ComingSoonTab(parent), is_disabled=True)

    def _add_nav_item(self, name: str, creation_func, is_disabled=False):
        """Adds a button to the sidebar and creates its corresponding content frame."""
        frame = creation_func(self.content_frame)
        self.content_frames[name] = frame
        
        default_text_color = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
        if is_disabled:
            default_text_color = ctk.ThemeManager.theme["CTkButton"]["text_color_disabled"]

        button = ctk.CTkButton(
            self.sidebar, text=name, command=lambda n=name: self._show_content_frame(n),
            fg_color="transparent", anchor="w", text_color=default_text_color
        )
        button.pack(fill="x", padx=10, pady=5)
        
        if is_disabled:
            button.configure(state="disabled")
        self.nav_buttons[name] = button

    def _show_content_frame(self, name: str):
        """Shows the specified content frame and updates nav button styles."""
        active_color = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        default_text_color = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
        active_text_color = ctk.ThemeManager.theme["CTkButton"]["text_color"]

        for frame_name, frame in self.content_frames.items():
            button = self.nav_buttons[frame_name]
            if button.cget("state") == "disabled":
                continue

            if frame_name == name:
                frame.grid(row=0, column=0, sticky="nsew") 
                button.configure(fg_color=active_color, text_color=active_text_color)
            else:
                frame.grid_forget() 
                button.configure(fg_color="transparent", text_color=default_text_color)

    def _mark_dirty(self, *args):
        if self.is_loading_settings: return
        if not self.has_unsaved_changes:
            self.has_unsaved_changes = True
            self.save_button.configure(state="normal")

    # --- Tab Creation Methods ---
    def _create_general_tab(self, parent):
        tab = GeneralTab(parent, self.theme_var)
        self.theme_var.trace_add("write", self._mark_dirty)
        return tab

    def _create_models_tab(self, parent):
        return ModelsTab(parent, self.locator, self.active_model_var, self.manage_provider_var, self.staged_model_lists, self._mark_dirty)

    def _create_api_keys_tab(self, parent):
        key_entries = {
            'gemini': ctk.CTkEntry(parent, show="*", placeholder_text="Set as GEMINI_API_KEY env var"),
            'openrouter': ctk.CTkEntry(parent, show="*", placeholder_text="Set as OPENROUTER_API_KEY env var"),
            'ollama': ctk.CTkEntry(parent)
        }
        test_model_vars = {
            'gemini': self.gemini_test_model_var,
            'openrouter': self.openrouter_test_model_var,
            'ollama': self.ollama_test_model_var
        }
        status_labels = {
            'gemini': ctk.CTkLabel(parent, text="●", text_color="gray", font=ctk.CTkFont(size=20)),
            'openrouter': ctk.CTkLabel(parent, text="●", text_color="gray", font=ctk.CTkFont(size=20)),
            'ollama': ctk.CTkLabel(parent, text="●", text_color="gray", font=ctk.CTkFont(size=20))
        }
        return ApiKeysTab(parent, key_entries, test_model_vars, status_labels, self.test_connection, self._mark_dirty)

    def _create_hotkeys_tab(self, parent):
        chat_entry = ctk.CTkEntry(parent)
        screen_entry = ctk.CTkEntry(parent)
        return HotkeysTab(parent, chat_entry, screen_entry, self._mark_dirty)

    def _create_plugins_tab(self, parent):
        return PluginsTab(parent, self.plugin_screencapture_enabled_var, self._mark_dirty)

    def _on_model_list_changed(self, *args):
        """Callback to update API key tab when model list changes in model tab."""
        self.content_frames["API Keys"].update_test_model_dropdowns(self.staged_model_lists)

    def on_connection_test_result(self, provider: str, success: bool):
        self.logger.debug(f"Received connection test result: {provider} -> {success}")
        self.after(0, self.update_status, provider, success)

    def update_status(self, provider: str, success: bool | None | str):
        color = "gray" if success is None else "orange" if success == "testing" else "green" if success else "red"
        status_label = getattr(self.content_frames["API Keys"], f"{provider}_status", None)
        if status_label:
            status_label.configure(text_color=color)

    def load_settings(self):
        self.is_loading_settings = True
        self.has_unsaved_changes = False
        self.save_button.configure(state="disabled")

        ui_config = self.config.get_config("ui_config.json")
        models_config = self.config.get_config("models_config.json")
        system_config = self.config.get_config("system_config.json")

        # General
        self.theme_var.set(ui_config.get("theme", "System"))
        if geometry := ui_config.get("settings_window", {}).get("geometry"):
            self.geometry(geometry)

        # Models
        providers_data = models_config.get("providers", {})
        self.staged_model_lists.clear()
        self.staged_model_lists.update({p: d.get("models", []) for p, d in providers_data.items()})
        
        models_tab = self.content_frames["Models"]
        provider_ids = list(self.staged_model_lists.keys())
        models_tab.set_provider_options(provider_ids)
        
        active_provider = models_config.get("active_provider")
        active_model = models_config.get("active_model")
        formatted_active_model = f"{active_provider}/{active_model}"
        all_models_formatted = [f"{p}/{m}" for p, ml in self.staged_model_lists.items() for m in ml]

        if active_model and formatted_active_model in all_models_formatted:
            self.active_model_var.set(formatted_active_model)
        elif all_models_formatted:
            self.active_model_var.set(all_models_formatted[0])
            active_provider, _ = all_models_formatted[0].split("/", 1)
        else:
            self.active_model_var.set("")

        if active_provider and active_provider in provider_ids:
            self.manage_provider_var.set(active_provider)
        elif provider_ids:
            self.manage_provider_var.set(provider_ids[0])
        else:
            self.manage_provider_var.set("")

        # API Keys
        api_keys_tab = self.content_frames["API Keys"]
        api_keys_tab.gemini_key_entry.delete(0, "end")
        api_keys_tab.gemini_key_entry.insert(0, providers_data.get("gemini", {}).get("api_key", ""))
        api_keys_tab.openrouter_key_entry.delete(0, "end")
        api_keys_tab.openrouter_key_entry.insert(0, providers_data.get("openrouter", {}).get("api_key", ""))
        api_keys_tab.ollama_url_entry.delete(0, "end")
        api_keys_tab.ollama_url_entry.insert(0, providers_data.get("ollama", {}).get("base_url", "http://localhost:11434"))
        api_keys_tab.update_test_model_dropdowns(self.staged_model_lists)
        self.update_status("gemini", None)
        self.update_status("openrouter", None)
        self.update_status("ollama", None)

        # Hotkeys
        hotkeys_tab = self.content_frames["Hotkeys"]
        hotkeys_tab.children['!ctkentry'].delete(0, "end")
        hotkeys_tab.children['!ctkentry'].insert(0, system_config.get("hotkeys", {}).get("open_chat", "<ctrl>+<shift>+<space>"))
        hotkeys_tab.children['!ctkentry2'].delete(0, "end")
        hotkeys_tab.children['!ctkentry2'].insert(0, system_config.get("hotkeys", {}).get("screen_capture", "<ctrl>+<shift>+x"))

        # Plugins
        plugin_config = system_config.get("plugins", {}).get("ScreenCapture", {})
        self.plugin_screencapture_enabled_var.set("on" if plugin_config.get("enabled", True) else "off")

        self.is_loading_settings = False

    def save_settings(self):
        self.logger.info("Saving settings...")
        
        ui_config = self.config.get_config("ui_config.json")
        models_config = self.config.get_config("models_config.json")
        system_config = self.config.get_config("system_config.json")

        # UI
        ui_config["theme"] = self.theme_var.get()
        self._save_geometry()
        self.config.save_config("ui_config.json", ui_config)
        ctk.set_appearance_mode(self.theme_var.get().lower())
        
        # Models
        if "/" in (active_model_str := self.active_model_var.get()):
            provider, model = active_model_str.split("/", 1)
            models_config["active_provider"] = provider
            models_config["active_model"] = model
        else:
            models_config["active_provider"] = self.manage_provider_var.get()
            models_config["active_model"] = ""
        
        api_keys_tab = self.content_frames["API Keys"]
        models_config["providers"]["gemini"]["api_key"] = api_keys_tab.gemini_key_entry.get()
        models_config["providers"]["openrouter"]["api_key"] = api_keys_tab.openrouter_key_entry.get()
        models_config["providers"]["ollama"]["base_url"] = api_keys_tab.ollama_url_entry.get()
        
        for provider_id, models_list in self.staged_model_lists.items():
            if provider_id in models_config["providers"]:
                models_config["providers"][provider_id]["models"] = models_list
        self.config.save_config("models_config.json", models_config)
        
        # System
        hotkeys_tab = self.content_frames["Hotkeys"]
        system_config["hotkeys"]["open_chat"] = hotkeys_tab.children['!ctkentry'].get()
        system_config["hotkeys"]["screen_capture"] = hotkeys_tab.children['!ctkentry2'].get()
        system_config.setdefault("plugins", {}).setdefault("ScreenCapture", {})
        system_config["plugins"]["ScreenCapture"]["enabled"] = (self.plugin_screencapture_enabled_var.get() == "on")
        self.config.save_config("system_config.json", system_config)

        self.publish_async_event("UI_EVENT.SETTINGS_CHANGED")
        
        self.has_unsaved_changes = False
        self.save_button.configure(state="disabled")
        self.hide(force=True)

    def _save_geometry(self):
        ui_config = self.config.get_config("ui_config.json")
        ui_config.setdefault("settings_window", {})["geometry"] = self.geometry()
        self.config.save_config("ui_config.json", ui_config)

    def test_connection(self, provider: str):
        self.logger.info(f"Requesting connection test for: {provider}")
        self.update_status(provider, "testing")

        api_keys_tab = self.content_frames["API Keys"]
        key_or_url, model_name = "", ""
        if provider == "gemini": 
            key_or_url = api_keys_tab.gemini_key_entry.get()
            model_name = self.gemini_test_model_var.get()
        elif provider == "openrouter": 
            key_or_url = api_keys_tab.openrouter_key_entry.get()
            model_name = self.openrouter_test_model_var.get()
        elif provider == "ollama": 
            key_or_url = api_keys_tab.ollama_url_entry.get()
            model_name = self.ollama_test_model_var.get()

        if not model_name:
            self.logger.warning(f"No model selected for {provider} test.")
            messagebox.showwarning("Test Failed", f"Please select a model for {provider} to test.")
            self.update_status(provider, False)
            return

        self.publish_async_event("API_EVENT.TEST_CONNECTION", provider=provider, value=key_or_url, model=model_name, timeout=5)
        
    def publish_async_event(self, event_type: str, *args, **kwargs):
        app = self.locator.resolve("app")
        async_loop = getattr(app, "async_loop", None)
        if not async_loop:
            self.logger.warning("Async loop not available. Cannot publish event.")
            return
        coro = self.events.publish(event_type, *args, **kwargs)
        asyncio.run_coroutine_threadsafe(coro, async_loop)

    def show(self):
        self.load_settings()
        self.deiconify()
        self.lift()
        self.focus_force()
        self.is_visible = True
        
    def hide(self, force: bool = False):
        if self.has_unsaved_changes and not force:
            if not messagebox.askyesno("Unsaved Changes", "You have unsaved changes. Are you sure you want to close without saving?"):
                return
        self._save_geometry()
        self.has_unsaved_changes = False
        self.save_button.configure(state="disabled")
        self.withdraw()
        self.is_visible = False