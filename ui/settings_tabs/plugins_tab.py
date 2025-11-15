# file: ui/settings_tabs/plugins_tab.py
import customtkinter as ctk

class PluginsTab(ctk.CTkFrame):
    """Tab for managing plugin settings."""
    def __init__(self, master, screencapture_enabled_var, mark_dirty_callback, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.grid_columnconfigure(1, weight=1)
        
        # --- Screen Capture Plugin ---
        ctk.CTkLabel(self, text="Screen Capture Plugin", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        plugin_screencapture_checkbox = ctk.CTkCheckBox(
            self,
            text="Enable Plugin (Hotkeys will be disabled if unchecked)",
            variable=screencapture_enabled_var,
            onvalue="on",
            offvalue="off"
        )
        plugin_screencapture_checkbox.grid(row=1, column=0, columnspan=2, padx=15, pady=5, sticky="w")
        
        screencapture_enabled_var.trace_add("write", mark_dirty_callback)
