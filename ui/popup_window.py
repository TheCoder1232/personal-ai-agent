# file: ui/popup_window.py

import logging
import asyncio
import customtkinter as ctk
from tkhtmlview import HTMLScrolledText
from core.service_locator import locator
from core.event_dispatcher import EventDispatcher
from core.agent import Agent
import markdown
import threading
from typing import Optional
from utils.config_loader import ConfigLoader # <-- NEW IMPORT

class PopupWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        
        # --- NEW: Service/Config setup ---
        self.master = master # Store master for async loop access
        self.locator = locator
        self.events: EventDispatcher = self.locator.resolve("event_dispatcher")
        self.config: ConfigLoader = self.locator.resolve("config_loader")
        self.agent: Agent = self.locator.resolve("agent")
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.title("Personal AI Agent")
        
        # --- NEW: Load geometry from config ---
        ui_config = self.config.get_config("ui_config.json")
        geometry = ui_config.get("popup_window", {}).get("geometry", "400x600")
        self.geometry(geometry)
        self.last_geometry = geometry
        # --- END NEW ---

        self.attributes("-topmost", True)
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- Chat History (Markdown Renderer) ---
        self.chat_history_frame = ctk.CTkFrame(self)
        self.chat_history_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        self.chat_history_frame.grid_rowconfigure(0, weight=1)
        self.chat_history_frame.grid_columnconfigure(0, weight=1)
        
        # --- MODIFIED: Base HTML (compacted) ---
        self.base_html = """<style>
            body { 
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, "Open Sans", "Helvetica Neue", sans-serif;
                color: #E0E0E0; background-color: #2B2B2B; line-height: 1.6;
            }
            p { margin: 0; }
            pre { background-color: #1E1E1E; padding: 10px; border-radius: 5px; overflow-x: auto; font-family: 'Courier New', Courier, monospace; }
            code { font-family: 'Courier New', Courier, monospace; background-color: #333; padding: 2px 4px; border-radius: 3px; }
            b { color: #4E9ADF; }
        </style>"""
        self.current_chat_html = self.base_html
        
        self.chat_history = HTMLScrolledText(
            self.chat_history_frame,
            html=self.current_chat_html
        )
        self.chat_history.grid(row=0, column=0, sticky="nsew")

        # --- MODIFIED: Use CTkTextbox for multi-line ---
        self.input_entry = ctk.CTkTextbox(
            self,
            height=60 # Start small, it will expand
        )
        self.input_entry.grid(row=1, column=0, sticky="nsew", padx=(5, 0), pady=(0, 5))
        
        # --- MODIFIED: Bindings for Ctrl+Enter and Shift+Enter ---
        self.input_entry.bind("<KeyRelease-Return>", self.on_key_release)
        # Removed old <Return> and <Control-Return> bindings

        # --- Attachment Indicator (Unchanged) ---
        self.attachment_label = ctk.CTkLabel(self, text="📎 Screenshot Attached", text_color="gray")
        # We will .grid() this only when needed

        # --- Send Button (Unchanged) ---
        self.send_button = ctk.CTkButton(
            self, 
            text="Send", 
            width=60,
            command=self.on_send
        )
        self.send_button.grid(row=1, column=1, sticky="nsew", padx=5, pady=(0, 5))
        
        # --- Streaming variables (Unchanged) ---
        self.streaming_lock = threading.Lock()
        self.current_stream_id = "agent_response_0"
        self.current_stream_content = ""
        self.stream_count = 0

        # --- Subscribe to Events ---
        self.events.subscribe("API_EVENT.RESPONSE_CHUNK", self.on_response_chunk)
        self.events.subscribe("API_EVENT.REQUEST_COMPLETE", self.on_request_complete)
        self.events.subscribe("PLUGIN_EVENT.SCREEN_CAPTURED", self.on_screen_attached)
        self.events.subscribe("AGENT_EVENT.CLEAR_CONTEXT", self.on_context_cleared_externally) # <-- NEW

        self.withdraw()
        self.protocol("WM_DELETE_WINDOW", self.hide)
        self.bind("<Configure>", self._on_window_move) # <-- NEW
        self.is_visible = False

    # --- NEW: Key handler for chat shortcuts ---
    def on_key_release(self, event):
        """Handle key releases in the textbox."""
        if event.keysym == "Return":
            if event.state & 0x0001:  # Shift key is pressed
                # Just let the newline happen, do nothing
                pass
            elif event.state & 0x0004: # Control key is pressed
                # Ctrl+Enter: Send
                self.on_send()
            else:
                # Just Enter: Do nothing on release
                # (Prevents default "send" from simple Enter)
                pass
                
        # Auto-resize textbox
        self._auto_resize_textbox()

    # --- NEW: Auto-resize textbox method ---
    def _auto_resize_textbox(self):
        """Dynamically resize the textbox based on content."""
        # Get the number of lines
        num_lines = int(self.input_entry.index("end-1c").split('.')[0])
        new_height = num_lines * 20 # Approx 20px per line
        
        # Clamp height between 60 and 200
        new_height = max(60, min(new_height, 200))
        
        if new_height != self.input_entry.cget("height"):
             self.input_entry.configure(height=new_height)

    def on_screen_attached(self, *args, **kwargs):
        """Shows the 'Attachment' label in the UI thread."""
        self.after(0, self._show_attachment_label)
    
    # --- MODIFIED: Use grid_configure ---
    def _show_attachment_label(self):
        """Internal UI method to update the grid."""
        # Move entry and button
        self.input_entry.grid_configure(row=2)
        self.send_button.grid_configure(row=2)
        
        # Show label
        self.attachment_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)

    # --- MODIFIED: Use grid_configure ---
    def _hide_attachment_label(self):
        """Hides the label and resets the grid."""
        self.attachment_label.grid_forget()
        
        # Move entry and button back
        self.input_entry.grid_configure(row=1)
        self.send_button.grid_configure(row=1)
        
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0) # Clear old config

    def convert_md_to_html(self, md_content: str) -> str:
        """Converts markdown to HTML."""
        # Use 'fenced_code' for code blocks
        return markdown.markdown(md_content, extensions=['fenced_code', 'codehilite'])

    def append_to_history(self, html_content: str, element_id: Optional[str] = None):
        """
        Appends HTML content to the chat history.
        If element_id is provided, it replaces the content of that element.
        """
        with self.streaming_lock:
            if element_id:
                # This is a streaming update. Find and replace.
                start_tag = f'<div id="{element_id}">'
                end_tag = '</div>'
                
                start_index = self.current_chat_html.find(start_tag)
                
                if start_index != -1:
                    end_index = self.current_chat_html.find(end_tag, start_index)
                    self.current_chat_html = (
                        self.current_chat_html[:start_index] +
                        f'{start_tag}{html_content}{end_tag}' +
                        self.current_chat_html[end_index + len(end_tag):]
                    )
                else:
                    # Element not found, just append it
                    self.current_chat_html += f'{start_tag}{html_content}{end_tag}<br>'
            else:
                # This is a new, complete message
                self.current_chat_html += f"<div>{html_content}</div><br>"
        
        self.chat_history.set_html(self.current_chat_html)
        # Scroll to the bottom
        self.chat_history.see("end")

    # --- MODIFIED: Read from CTkTextbox and handle newlines ---
    def on_send(self, event=None):
        user_message = self.input_entry.get("1.0", "end-1c").strip()
        if not user_message:
            return
            
        self.logger.info(f"User query: {user_message}")
        self.input_entry.delete("1.0", "end")
        self._auto_resize_textbox() # Reset size
        
        # Display user message (now converting markdown AND newlines)
        user_message_html = user_message.replace('\n', '<br>')
        user_html = self.convert_md_to_html(f"**You:**\n\n{user_message_html}")
        self.append_to_history(user_html)
        
        # --- Start streaming state ---
        self.stream_count += 1
        self.current_stream_id = f"agent_response_{self.stream_count}"
        self.current_stream_content = ""
        
        # Show a "thinking" message
        self.append_to_history("<i>Thinking...</i>", self.current_stream_id)

        # --- Check for attachment ---
        has_attachment = self.agent.pending_image_data is not None
        if has_attachment:
            self.append_to_history("<i>(Screenshot attached to this message)</i>")
            self.after(0, self._hide_attachment_label) # Hide label after sending
        
        # Publish event for the agent
        self.publish_async_event(
            "AGENT_EVENT.QUERY_RECEIVED", 
            user_message=user_message,
            image_data=None # Agent will pick up pending_image_data
        )

    # --- MODIFIED: Handle newlines ---
    def on_response_chunk(self, chunk: str):
        """Event handler for a new response chunk (streaming)."""
        # This is called from the async thread
        with self.streaming_lock:
            self.current_stream_content += chunk
            
        # Convert markdown to HTML in the UI thread
        stream_content_html = self.current_stream_content.replace('\n', '<br>')
        html_chunk = self.convert_md_to_html(f"**Agent:**\n\n{stream_content_html}")
        
        # Schedule the UI update
        self.after(0, self.append_to_history, html_chunk, self.current_stream_id)
        
    # --- MODIFIED: Handle newlines ---
    def on_request_complete(self, full_response: str):
        """Event handler for the final response."""
        # This is called from the async thread
        
        # Final conversion of the full response
        full_response_html = full_response.replace('\n', '<br>')
        final_html = self.convert_md_to_html(f"**Agent:**\n\n{full_response_html}")
        
        # Schedule the final UI update
        self.after(0, self.append_to_history, final_html, self.current_stream_id)
        
        # Clear streaming state
        with self.streaming_lock:
            self.current_stream_content = ""

    # --- REMOVED: on_clear_context(self, event=None) ---
    # This logic is now handled by on_context_cleared_externally

    # --- NEW: Clear context logic (subscribes to event) ---
    def on_context_cleared_externally(self, *args):
        """Called when agent context is cleared (e.g., from global hotkey)."""
        self.after(0, self.clear_chat_ui)
        
    def clear_chat_ui(self):
        """Clears the chat UI."""
        self.logger.info("Clearing chat UI.")
        self.current_chat_html = self.base_html
        self.chat_history.set_html(self.current_chat_html)
        self.after(0, self._hide_attachment_label)

    # --- NEW: Window position saving ---
    def _on_window_move(self, event):
        """Debounce method to save window geometry on move/resize."""
        self.last_geometry = self.geometry()

    # --- (Unchanged) Safer async event publisher from code (1) ---
    def publish_async_event(self, event_type: str, *args, **kwargs):
        """Safely publishes an event to the asyncio loop from the UI thread."""
        async_loop = getattr(self.master, "async_loop", None)
        if not async_loop:
            self.logger.warning("Async loop not available. Cannot publish event.")
            return
        
        coro = self.events.publish(event_type, *args, **kwargs)
        asyncio.run_coroutine_threadsafe(coro, async_loop)

    # --- MODIFIED: Restore geometry on show ---
    def show(self):
        """Shows and focuses the popup window."""
        # Restore geometry
        ui_config = self.config.get_config("ui_config.json")
        geometry = ui_config.get("popup_window", {}).get("geometry", "400x600")
        self.geometry(geometry)

        self.deiconify()
        self.lift()
        self.focus_force()
        self.input_entry.focus_set()
        self.is_visible = True
        
    # --- MODIFIED: Save geometry on hide ---
    def hide(self):
        """Hides the window (called by 'X' button) and saves geometry."""
        # Save geometry on hide
        if self.last_geometry:
            ui_config = self.config.get_config("ui_config.json")
            ui_config.setdefault("popup_window", {})["geometry"] = self.last_geometry
            self.config.save_config("ui_config.json", ui_config)
            self.last_geometry = "" # Clear after saving
            
        self.withdraw()
        self.is_visible = False