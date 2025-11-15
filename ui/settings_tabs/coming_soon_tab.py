# file: ui/settings_tabs/coming_soon_tab.py
import customtkinter as ctk

class ComingSoonTab(ctk.CTkFrame):
    """A placeholder tab for features that are not yet implemented."""
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        label_frame = ctk.CTkFrame(self, fg_color="transparent")
        label_frame.grid(row=0, column=0, sticky="nsew")
        
        label_frame.grid_rowconfigure(0, weight=1)
        label_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            label_frame, 
            text="Coming Soon",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=ctk.ThemeManager.theme["CTkButton"]["text_color_disabled"]
        ).grid(row=0, column=0, sticky="nsew")
