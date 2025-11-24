# file: ui/settings_tabs/hotkeys_tab.py
import customtkinter as ctk

class HotkeysTab(ctk.CTkFrame):
    """Tab for configuring global hotkeys."""
    def __init__(self, master, mark_dirty_callback, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.grid_columnconfigure(1, weight=1)
        
        # Create entry widgets with self as parent
        self.chat_hotkey_entry = ctk.CTkEntry(self)
        self.screen_hotkey_entry = ctk.CTkEntry(self)
        
        ctk.CTkLabel(self, text="Open Chat:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.chat_hotkey_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(self, text="Screen Capture:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.screen_hotkey_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        self.chat_hotkey_entry.bind("<KeyRelease>", mark_dirty_callback)
        self.screen_hotkey_entry.bind("<KeyRelease>", mark_dirty_callback)
