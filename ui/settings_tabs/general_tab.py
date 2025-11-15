# file: ui/settings_tabs/general_tab.py
import customtkinter as ctk

class GeneralTab(ctk.CTkFrame):
    """Tab for general application settings like theme."""
    def __init__(self, master, theme_var, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        
        self.grid_columnconfigure(1, weight=1)
        
        ctk.CTkLabel(self, text="Theme:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        theme_menu = ctk.CTkOptionMenu(self, variable=theme_var, values=["System", "Dark", "Light"])
        theme_menu.grid(row=0, column=1, padx=10, pady=10, sticky="w")
