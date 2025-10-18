    # file: ui/popup_window.py

import logging
import asyncio
import customtkinter as ctk
from tkhtmlview import HTMLScrolledText
from core.service_locator import locator
from core.event_dispatcher import EventDispatcher

class PopupWindow(ctk.CTkToplevel):
    """
    The main chat popup window.
    Inherits from CTkToplevel.
    """
    def __init__(self, master):
        super().__init__(master)
        self.master = master # This is the main App instance
        self.locator = locator
        self.events: EventDispatcher = self.locator.resolve("event_dispatcher")
        self.logger = logging.getLogger(self.__class__.__name__)

        self.title("Personal AI Agent")
        self.geometry("400x600")
        self.attributes("-topmost", True)
        
        # --- Configure Grid ---
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- Chat History (Markdown Renderer) ---
        self.chat_history_frame = ctk.CTkFrame(self)
        self.chat_history_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        self.chat_history_frame.grid_rowconfigure(0, weight=1)
        self.chat_history_frame.grid_columnconfigure(0, weight=1)
        
        self.chat_history = HTMLScrolledText(
            self.chat_history_frame,
            background=self.chat_history_frame.cget("fg_color")[1], # Match CTk theme
            html="<style>body { font-family: sans-serif; color: white; }</style>"
        )
        self.chat_history.grid(row=0, column=0, sticky="nsew")

        # --- Text Input Box ---
        self.input_entry = ctk.CTkEntry(
            self, 
            placeholder_text="Type your message..."
        )
        self.input_entry.grid(row=1, column=0, sticky="nsew", padx=(5, 0), pady=(0, 5))
        self.input_entry.bind("<Return>", self.on_send)

        # --- Send Button ---
        self.send_button = ctk.CTkButton(
            self, 
            text="Send", 
            width=60,
            command=self.on_send
        )
        self.send_button.grid(row=1, column=1, sticky="nsew", padx=5, pady=(0, 5))
        
        # --- Subscribe to Events ---
        self.events.subscribe("API_EVENT.RESPONSE_CHUNK", self.on_response_chunk)
        self.events.subscribe("API_EVENT.REQUEST_COMPLETE", self.on_request_complete)

        # --- Window Configuration ---
        # Don't show it yet
        self.withdraw()
        # Handle the 'X' button
        self.protocol("WM_DELETE_WINDOW", self.hide)
        self.is_visible = False

    def on_send(self, event=None):
        """Called when the Send button is clicked or Enter is pressed."""
        user_message = self.input_entry.get()
        if not user_message.strip():
            return
            
        self.logger.info(f"User query: {user_message}")
        self.input_entry.delete(0, "end")
        
        # Display user message
        # We'll need a markdown converter later, for now just basic
        self.append_to_history(f"<b>You:</b><br>{user_message}")
        
        # Publish event for the agent (Phase 3) to process
        self.publish_async_event(
            "AGENT_EVENT.QUERY_RECEIVED", 
            user_message=user_message,
            image_data=None # We'll add this with screen capture
        )
        
        # Show a "thinking" message
        # We need a way to ID this message to update it later
        self.append_to_history("<p id='loading'><i>Thinking...</i></p>")

    def append_to_history(self, html_content):
        """Appends HTML content to the chat history."""
        # HTMLScrolledText doesn't expose a typed get_html() method; keep an internal buffer.
        if not hasattr(self, "history_html"):
            self.history_html = ""
        self.history_html += f"{html_content}<br>"
        self.chat_history.set_html(self.history_html)
        # TODO: Scroll to bottom
        
    def on_response_chunk(self, chunk: str):
        """Event handler for a new response chunk (streaming)."""
        # This is complex. For now, let's just log it.
        # A real implementation would update the "Thinking..." message.
        self.logger.debug(f"Received chunk: {chunk}")
        
    def on_request_complete(self, full_response: str):
        """Event handler for the final response."""
        # This is called from the async thread, so we must use .after()
        self.after(0, self._update_response, full_response)
        
    def _update_response(self, full_response: str):
        """Internal UI method to update the chat."""
        # This is a simplified version. A real one would find and
        # replace the "<p id='loading'>...</p>"
        self.logger.info("Updating chat with full response.")
        # For now, just append
        self.append_to_history(f"<b>Agent:</b><br>{full_response}")

    def publish_async_event(self, event_type: str, *args, **kwargs):
        """Safely publishes an event to the asyncio loop from the UI thread."""
        async_loop = getattr(self.master, "async_loop", None)
        if not async_loop:
            self.logger.warning("Async loop not available. Cannot publish event.")
            return
        
        coro = self.events.publish(event_type, *args, **kwargs)
        asyncio.run_coroutine_threadsafe(coro, async_loop)

    def show(self):
        """Shows and focuses the popup window."""
        self.deiconify()
        self.lift()
        self.focus_force()
        self.input_entry.focus_set()
        self.is_visible = True
        
    def hide(self):
        """Hides the window (called by 'X' button)."""
        self.withdraw()
        self.is_visible = False