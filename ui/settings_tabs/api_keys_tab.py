# file: ui/settings_tabs/api_keys_tab.py
import customtkinter as ctk

class ApiKeysTab(ctk.CTkFrame):
    """Tab for managing API keys and connection testing."""
    def __init__(self, master, test_model_vars, test_connection_callback, mark_dirty_callback, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.grid_columnconfigure(1, weight=1)

        # Store test model variables
        self.gemini_test_model_var = test_model_vars['gemini']
        self.openrouter_test_model_var = test_model_vars['openrouter']
        self.ollama_test_model_var = test_model_vars['ollama']

        # Create entry widgets and status labels inside this tab
        self.gemini_key_entry = ctk.CTkEntry(self, show="*", placeholder_text="Set as GEMINI_API_KEY env var")
        self.openrouter_key_entry = ctk.CTkEntry(self, show="*", placeholder_text="Set as OPENROUTER_API_KEY env var")
        self.ollama_url_entry = ctk.CTkEntry(self)

        self.gemini_status = ctk.CTkLabel(self, text="●", text_color="gray", font=ctk.CTkFont(size=20))
        self.openrouter_status = ctk.CTkLabel(self, text="●", text_color="gray", font=ctk.CTkFont(size=20))
        self.ollama_status = ctk.CTkLabel(self, text="●", text_color="gray", font=ctk.CTkFont(size=20))

        # --- Gemini ---
        ctk.CTkLabel(self, text="Gemini API Key:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.gemini_key_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        self.gemini_model_menu = ctk.CTkOptionMenu(self, variable=self.gemini_test_model_var, values=[])
        self.gemini_model_menu.grid(row=0, column=2, padx=(0, 5), pady=10)
        self.gemini_model_menu.set("")
        
        ctk.CTkButton(self, text="Test", command=lambda: test_connection_callback("gemini")).grid(row=0, column=3, padx=(5, 10), pady=10)
        self.gemini_status.grid(row=0, column=4, padx=5, pady=10)
        
        # --- OpenRouter ---
        ctk.CTkLabel(self, text="OpenRouter API Key:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.openrouter_key_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        self.openrouter_model_menu = ctk.CTkOptionMenu(self, variable=self.openrouter_test_model_var, values=[])
        self.openrouter_model_menu.grid(row=1, column=2, padx=(0, 5), pady=10)
        self.openrouter_model_menu.set("")

        ctk.CTkButton(self, text="Test", command=lambda: test_connection_callback("openrouter")).grid(row=1, column=3, padx=(5, 10), pady=10)
        self.openrouter_status.grid(row=1, column=4, padx=5, pady=10)

        # --- Ollama ---
        ctk.CTkLabel(self, text="Ollama Base URL:").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.ollama_url_entry.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        self.ollama_model_menu = ctk.CTkOptionMenu(self, variable=self.ollama_test_model_var, values=[])
        self.ollama_model_menu.grid(row=2, column=2, padx=(0, 5), pady=10)
        self.ollama_model_menu.set("")

        ctk.CTkButton(self, text="Test", command=lambda: test_connection_callback("ollama")).grid(row=2, column=3, padx=(5, 10), pady=10)
        self.ollama_status.grid(row=2, column=4, padx=5, pady=10)

        self.gemini_key_entry.bind("<KeyRelease>", mark_dirty_callback)
        self.openrouter_key_entry.bind("<KeyRelease>", mark_dirty_callback)
        self.ollama_url_entry.bind("<KeyRelease>", mark_dirty_callback)

    def update_test_model_dropdowns(self, staged_model_lists):
        """Populates the model dropdowns on the API Keys tab."""
        # --- Gemini ---
        gemini_models = staged_model_lists.get("gemini", [])
        self.gemini_model_menu.configure(values=gemini_models)
        current_gemini = self.gemini_test_model_var.get()
        if current_gemini in gemini_models:
            self.gemini_model_menu.set(current_gemini)
        elif gemini_models:
            self.gemini_test_model_var.set(gemini_models[0])
        else:
            self.gemini_test_model_var.set("")
            self.gemini_model_menu.set("")

        # --- OpenRouter ---
        openrouter_models = staged_model_lists.get("openrouter", [])
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
        ollama_models = staged_model_lists.get("ollama", [])
        self.ollama_model_menu.configure(values=ollama_models)
        current_ollama = self.ollama_test_model_var.get()
        if current_ollama in ollama_models:
            self.ollama_model_menu.set(current_ollama)
        elif ollama_models:
            self.ollama_test_model_var.set(ollama_models[0])
        else:
            self.ollama_test_model_var.set("")
            self.ollama_model_menu.set("")
