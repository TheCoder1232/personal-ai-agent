# file: ui/settings_tabs/models_tab.py
import customtkinter as ctk
import tkinter as tk

class ModelsTab(ctk.CTkFrame):
    """Tab for managing AI models."""
    def __init__(self, master, locator, active_model_var, manage_provider_var, staged_model_lists, mark_dirty_callback, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        
        self.locator = locator
        self.logger = self.locator.resolve("logger")
        self.events = self.locator.resolve("event_dispatcher")
        
        self.active_model_var = active_model_var
        self.manage_provider_var = manage_provider_var
        self.staged_model_lists = staged_model_lists
        self._mark_dirty = mark_dirty_callback

        self.grid_columnconfigure(1, weight=1)

        # --- Row 0 - Manage Provider ---
        ctk.CTkLabel(self, text="Manage Provider:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.manage_provider_dropdown = ctk.CTkOptionMenu(self, variable=self.manage_provider_var)
        self.manage_provider_dropdown.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # --- Row 1 - Active Model ---
        ctk.CTkLabel(self, text="Active Model:").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.model_dropdown = ctk.CTkOptionMenu(self, variable=self.active_model_var, values=[])
        self.model_dropdown.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        self.active_model_var.trace_add("write", self._mark_dirty)

        # --- Row 2 & 3 - Separator ---
        ctk.CTkLabel(self, text="Manage Models", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, columnspan=2, padx=10, pady=(10,0), sticky="w")
        ctk.CTkFrame(self, height=2).grid(row=3, column=0, columnspan=2, padx=10, pady=(5,10), sticky="ew")

        # --- Row 4 - Model List ---
        self.model_list_frame = ctk.CTkScrollableFrame(self)
        self.model_list_frame.grid(row=4, column=0, columnspan=2, padx=10, pady=0, sticky="nsew")
        self.grid_rowconfigure(4, weight=1)

        # --- Row 5 - Add Model Frame ---
        add_frame = ctk.CTkFrame(self)
        add_frame.grid(row=5, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        add_frame.grid_columnconfigure(0, weight=1)

        self.new_model_entry = ctk.CTkEntry(add_frame, placeholder_text="Enter model name (e.g., llama3-8b)")
        self.new_model_entry.grid(row=0, column=0, padx=(0, 5), pady=0, sticky="ew")
        self.new_model_entry.bind("<Return>", self._add_model_to_ui)

        self.add_model_button = ctk.CTkButton(add_frame, text="Add Model", width=100, command=self._add_model_to_ui)
        self.add_model_button.grid(row=0, column=1, padx=(5, 0), pady=0)

        self.manage_provider_var.trace_add("write", self._on_manage_provider_changed)

    def _on_manage_provider_changed(self, *args):
        provider_id = self.manage_provider_var.get()
        if provider_id:
            self.update_model_ui(provider_id)
            self.update_active_model_dropdown(provider_id)

    def update_active_model_dropdown(self, provider_id: str):
        self.logger.debug(f"Updating active model dropdown for provider: {provider_id}")
        
        models_list = self.staged_model_lists.get(provider_id, [])
        formatted_models = [f"{provider_id}/{model}" for model in models_list]
        
        current_active_model = self.active_model_var.get()
        
        self.model_dropdown.configure(values=formatted_models)
        
        if current_active_model in formatted_models:
            self.model_dropdown.set(current_active_model)
        elif formatted_models:
            self.active_model_var.set(formatted_models[0])
        else:
            self.active_model_var.set("")
            self.model_dropdown.set("")

    def update_model_ui(self, provider_id: str):
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

            menu_button = ctk.CTkButton(frame, text="⋮", width=30)
            menu_button.grid(row=0, column=1, padx=5, pady=5, sticky="e")
            menu_button.configure(command=lambda p=provider_id, m=model_name, w=menu_button: self._show_model_menu(p, m, w))

    def _add_model_to_ui(self, event=None):
        provider_id = self.manage_provider_var.get()
        new_model = self.new_model_entry.get().strip()
        
        if not provider_id:
            self.logger.warning("No provider selected. Cannot add model.")
            return
            
        if new_model and new_model not in self.staged_model_lists[provider_id]:
            self.logger.info(f"Staging new model '{new_model}' for provider '{provider_id}'")
            self.staged_model_lists[provider_id].append(new_model)
            self.update_model_ui(provider_id)
            self.update_active_model_dropdown(provider_id)
            self.events.publish("SETTINGS_EVENT.MODEL_LIST_CHANGED")
            self.new_model_entry.delete(0, "end")
            self._mark_dirty() 
        else:
            self.logger.warning(f"Model '{new_model}' is empty or already exists.")

    def _remove_model_from_ui(self, provider_id: str, model_name: str):
        if model_name in self.staged_model_lists[provider_id]:
            self.logger.info(f"Unstaging model '{model_name}' for provider '{provider_id}'")
            self.staged_model_lists[provider_id].remove(model_name)
            self.update_model_ui(provider_id)
            self.update_active_model_dropdown(provider_id)
            self.events.publish("SETTINGS_EVENT.MODEL_LIST_CHANGED")
            self._mark_dirty()
        else:
            self.logger.warning(f"Could not find model '{model_name}' to remove.")

    def _show_model_menu(self, provider_id: str, model_name: str, widget: ctk.CTkButton):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Remove", command=lambda: self._remove_model_from_ui(provider_id, model_name))
        menu.add_command(label="Set as Default", command=lambda: self._set_model_as_default(provider_id, model_name))
        menu.add_command(label="Test Model", command=lambda: self._test_model(provider_id, model_name))
        menu.post(widget.winfo_rootx(), widget.winfo_rooty() + widget.winfo_height())

    def _set_model_as_default(self, provider_id: str, model_name: str):
        formatted_model = f"{provider_id}/{model_name}"
        all_models = []
        for p, m_list in self.staged_model_lists.items():
            for m in m_list:
                all_models.append(f"{p}/{m}")

        if formatted_model in all_models:
            self.active_model_var.set(formatted_model)
            self.logger.info(f"Set active model to: {formatted_model}")
            self._mark_dirty()
        else:
            self.logger.warning(f"Could not set default model: '{formatted_model}' not found.")

    def _test_model(self, provider_id: str, model_name: str):
        self.logger.info(f"Requesting test for model: {provider_id}/{model_name}")
        # This event needs to be published to the main async loop
        app = self.locator.resolve("app")
        async_loop = getattr(app, "async_loop", None)
        if async_loop:
            coro = self.events.publish("API_EVENT.TEST_MODEL", provider=provider_id, model=model_name, timeout=5)
            asyncio.run_coroutine_threadsafe(coro, async_loop)
        else:
            self.logger.error("Could not find async loop to publish test event.")

    def set_provider_options(self, provider_ids):
        self.manage_provider_dropdown.configure(values=provider_ids)
