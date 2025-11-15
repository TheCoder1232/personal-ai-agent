# file: ui/popup_window.py

import logging
import asyncio
import customtkinter as ctk
from tkhtmlview import HTMLLabel
from core.service_locator import locator
from core.event_dispatcher import EventDispatcher
from core.agent import Agent
import threading
from typing import Optional, Dict
from utils.config_loader import ConfigLoader
from .ui_utils import UIConstants, GridPosition
from .html_formatter import HTMLFormatter

class PopupWindow(ctk.CTkToplevel):
    """Main popup window for AI agent interaction"""
    
    def __init__(self, master):
        super().__init__(master)
        
        # Core dependencies
        self.master = master
        self.locator = locator
        self.logger = self._setup_logger()
        
        # Initialize services with error handling
        self._init_services()
        
        # Thread safety
        self.stream_lock = threading.Lock()
        self.stream_is_active = False
        self.ui_update_pending = False
        
        # Setup window
        self._setup_window()
        
        # Initialize formatter
        self.formatter = HTMLFormatter(self._get_theme_colors())
        
        # State management
        self.chat_messages = []
        self.current_stream_id = "agent_response_0"
        self.current_stream_content = ""
        self.stream_count = 0
        self.is_visible = False
        self.has_attachment = False
        
        # Setup UI components
        self._setup_ui()
        
        # Subscribe to events
        self._subscribe_events()
        
        # Window behavior
        self.withdraw()
        self.protocol("WM_DELETE_WINDOW", self.hide)
        self.bind("<Configure>", self._on_window_move)
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logger with null check"""
        logger = logging.getLogger(self.__class__.__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    def _init_services(self):
        """Initialize services with error handling"""
        try:
            self.events: EventDispatcher = self.locator.resolve("event_dispatcher")
            self.config: ConfigLoader = self.locator.resolve("config_loader")
            self.agent: Agent = self.locator.resolve("agent")
        except Exception as e:
            self.logger.error(f"Failed to initialize services: {e}")
            raise RuntimeError(f"Service initialization failed: {e}")
    
    def _setup_window(self):
        """Configure window properties"""
        self.title("Personal AI Agent")
        
        ui_config = self.config.get_config("ui_config.json")
        geometry = ui_config.get("popup_window", {}).get(
            "geometry", 
            UIConstants.DEFAULT_GEOMETRY
        )
        self.geometry(geometry)
        self.last_geometry = geometry
        self.attributes("-topmost", True)
        
        # Grid configuration
        # --- MODIFIED: Add BRANCH_ROW ---
        self.grid_rowconfigure(GridPosition.BRANCH_ROW, weight=0) # For visualization
        self.grid_rowconfigure(GridPosition.CHAT_HISTORY_ROW, weight=1)
        self.grid_rowconfigure(GridPosition.ATTACHMENT_ROW, weight=0)
        self.grid_rowconfigure(GridPosition.INPUT_ROW, weight=0)
        
        self.grid_columnconfigure(GridPosition.MAIN_COLUMN, weight=1)
        self.grid_columnconfigure(GridPosition.CLEAR_BUTTON_COLUMN, weight=0)
        self.grid_columnconfigure(GridPosition.SEND_BUTTON_COLUMN, weight=0)

    def _get_theme_colors(self) -> Dict[str, str]:
        """Extract theme colors with fallbacks"""
        try:
            return {
                'bg': ctk.ThemeManager.theme["CTkScrollableFrame"]["fg_color"][1],
                'text': ctk.ThemeManager.theme["CTkLabel"]["text_color"][1],
                'code_bg': ctk.ThemeManager.theme["CTkFrame"]["fg_color"][1],
                'inline_bg': ctk.ThemeManager.theme["CTkButton"]["fg_color"][1],
                'link': "#4E9ADF"
            }
        except Exception as e:
            self.logger.warning(f"Could not read theme colors: {e}. Using defaults.")
            return {
                'bg': "#F9F9F9",
                'text': "#1C1C1C",
                'code_bg': "#E5E5E5",
                'inline_bg': "#DCE4EE",
                'link': "#4E9ADF"
            }
    
    def _setup_ui(self):
        """Setup all UI components"""
        
        # --- NEW: Branch visualization placeholder ---
        self.branch_frame = ctk.CTkFrame(self, height=30, fg_color="transparent")
        self.branch_frame.grid(
            row=GridPosition.BRANCH_ROW,
            column=GridPosition.MAIN_COLUMN,
            columnspan=3,
            sticky="ew",
            padx=UIConstants.PADDING_SMALL,
            pady=(UIConstants.PADDING_SMALL, 0)
        )
        self.branch_label = ctk.CTkLabel(self.branch_frame, text="Current Branch: main", text_color="gray")
        self.branch_label.pack(side="left", padx=UIConstants.PADDING_SMALL)
        # TODO: Add buttons or a dropdown here to switch branches
        
        # Chat history frame
        self.chat_history_frame = ctk.CTkScrollableFrame(self)
        self.chat_history_frame.grid(
            row=GridPosition.CHAT_HISTORY_ROW, # --- MODIFIED ---
            column=GridPosition.MAIN_COLUMN,
            columnspan=3,
            sticky="nsew",
            padx=UIConstants.PADDING_SMALL,
            pady=UIConstants.PADDING_SMALL
        )

        self.chat_history_frame._scrollbar.grid_forget()
        
        colors = self.formatter.colors
        
        # Chat display with proper scrolling
        self.chat_history = HTMLLabel(
            self.chat_history_frame,
            background=colors['bg'],
            fg=colors['text'],
            font=("Segoe UI", 12),
            html="<html><body></body></html>"
        )
        self.chat_history.pack(fill="both", expand=True, padx=UIConstants.PADDING_MEDIUM, pady=UIConstants.PADDING_MEDIUM)
        
        # Fix scrollbar issue - bind to canvas
        self.chat_history_frame.bind("<Configure>", lambda e: self._fix_scrollbar())
        
        # Attachment label (hidden by default)
        self.attachment_label = ctk.CTkLabel(
            self,
            text="📎 Screenshot Attached",
            text_color="gray"
        )
        
        # Remove attachment button
        self.remove_attachment_btn = ctk.CTkButton(
            self,
            text="✕",
            width=30,
            command=self._remove_attachment,
            fg_color="transparent",
            hover_color=("gray70", "gray30")
        )
        
        # Input textbox
        self.input_entry = ctk.CTkTextbox(self, height=UIConstants.INPUT_MIN_HEIGHT)
        self.input_entry.grid(
            row=GridPosition.INPUT_ROW, # --- MODIFIED ---
            column=GridPosition.MAIN_COLUMN,
            sticky="nsew",
            padx=(UIConstants.PADDING_SMALL, 0),
            pady=(0, UIConstants.PADDING_SMALL)
        )
        self.input_entry.bind("<KeyRelease>", self._on_key_release)
        self.input_entry.bind("<Shift-Return>", self._on_shift_return)
        self.input_entry.bind("<Control-Return>", lambda e: self.on_send())
        
        # Control buttons
        self._setup_buttons()
        
        # Keyboard shortcuts hint
        self.shortcuts_label = ctk.CTkLabel(
            self,
            text="Ctrl+Enter: Send | Shift+Enter: New line | Ctrl+L: Clear",
            text_color="gray",
            font=("Segoe UI", 9)
        )
        
        # Bind global shortcuts
        self.bind("<Control-l>", lambda e: self.on_clear_chat())
        self.bind("<Control-n>", lambda e: self.on_new_chat())
    
    def _setup_buttons(self):
        """Setup control buttons"""
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(
            row=GridPosition.INPUT_ROW,
            column=GridPosition.CLEAR_BUTTON_COLUMN,
            columnspan=2,
            sticky="nsew",
            padx=UIConstants.PADDING_SMALL,
            pady=(0, UIConstants.PADDING_SMALL)
        )
        
        # New Chat button
        self.new_chat_button = ctk.CTkButton(
            button_frame,
            text="New",
            width=UIConstants.BUTTON_WIDTH,
            command=self.on_new_chat
        )
        self.new_chat_button.pack(side="left", padx=(0, UIConstants.PADDING_SMALL))
        
        # Clear button
        self.clear_button = ctk.CTkButton(
            button_frame,
            text="Clear",
            width=UIConstants.BUTTON_WIDTH,
            command=self.on_clear_chat
        )
        self.clear_button.pack(side="left", padx=(0, UIConstants.PADDING_SMALL))
        
        # Send button
        self.send_button = ctk.CTkButton(
            button_frame,
            text="Send",
            width=UIConstants.BUTTON_WIDTH,
            command=self.on_send
        )
        self.send_button.pack(side="left")
    
    def _fix_scrollbar(self):
        """Fix scrollbar interaction"""
        try:
            canvas = self.chat_history_frame._parent_canvas
            scrollbar = self.chat_history_frame._scrollbar
            if canvas and scrollbar:
                # Ensure scrollbar is properly connected
                canvas.configure(yscrollcommand=scrollbar.set)
                scrollbar.configure(command=canvas.yview)
        except Exception as e:
            self.logger.debug(f"Scrollbar fix attempt: {e}")
    
    def _subscribe_events(self):
        """Subscribe to application events"""
        self.events.subscribe("API_EVENT.RESPONSE_CHUNK", self.on_response_chunk)
        self.events.subscribe("API_EVENT.REQUEST_COMPLETE", self.on_request_complete)
        self.events.subscribe("PLUGIN_EVENT.SCREEN_CAPTURED", self.on_screen_attached)
        self.events.subscribe("AGENT_EVENT.CLEAR_CONTEXT", self.on_context_cleared_externally)
        self.events.subscribe("CONTEXT_EVENT.BRANCH_CHANGED", self.on_branch_changed)
    
    def _on_key_release(self, event):
        """Handle key release events"""
        if event.keysym == "Return":
            # Check modifiers
            shift_pressed = bool(event.state & 0x0001)
            ctrl_pressed = bool(event.state & 0x0004)
            
            if shift_pressed:
                # Shift+Enter: new line (default behavior, do nothing)
                pass
            elif ctrl_pressed:
                # Ctrl+Enter: send message
                self.on_send()
                return "break"  # Prevent default
            else:
                # Plain Enter: do nothing (or customize)
                pass
        
        self._auto_resize_textbox()
    
    def _on_shift_return(self, event):
        """Handle Shift+Return for new line"""
        # Default behavior is to insert newline, so we just resize
        self.after(10, self._auto_resize_textbox)
        return None  # Allow default behavior
    
    def _auto_resize_textbox(self):
        """Auto-resize input textbox based on content"""
        try:
            num_lines = int(self.input_entry.index("end-1c").split('.')[0])
            new_height = max(
                UIConstants.INPUT_MIN_HEIGHT,
                min(num_lines * UIConstants.INPUT_LINE_HEIGHT, UIConstants.INPUT_MAX_HEIGHT)
            )
            
            current_height = self.input_entry.cget("height")
            if new_height != current_height:
                self.input_entry.configure(height=new_height)
        except Exception as e:
            self.logger.debug(f"Textbox resize error: {e}")
    
    def on_screen_attached(self, *args, **kwargs):
        """Handle screenshot attachment"""
        self.has_attachment = True
        self.after(0, self._show_attachment_label)
    
    def _show_attachment_label(self):
        """Show attachment indicator"""
        self.attachment_label.grid(
            row=GridPosition.ATTACHMENT_ROW,
            column=GridPosition.MAIN_COLUMN,
            sticky="w",
            padx=UIConstants.PADDING_MEDIUM,
            pady=(0, UIConstants.PADDING_SMALL)
        )
        self.remove_attachment_btn.grid(
            row=GridPosition.ATTACHMENT_ROW,
            column=GridPosition.CLEAR_BUTTON_COLUMN,
            sticky="e",
            padx=UIConstants.PADDING_SMALL,
            pady=(0, UIConstants.PADDING_SMALL)
        )
    
    def _hide_attachment_label(self):
        """Hide attachment indicator"""
        self.has_attachment = False
        self.attachment_label.grid_forget()
        self.remove_attachment_btn.grid_forget()
    
    def _remove_attachment(self):
        """Remove screenshot attachment"""
        if self.agent and hasattr(self.agent, 'pending_image_data'):
            self.agent.pending_image_data = None
        self._hide_attachment_label()
        self.logger.info("Screenshot attachment removed")
    
    def _validate_message(self, message: str) -> tuple[bool, str]:
        """Validate user message"""
        if not message:
            return False, "Message cannot be empty"
        
        if len(message) > UIConstants.MAX_MESSAGE_LENGTH:
            return False, f"Message too long (max {UIConstants.MAX_MESSAGE_LENGTH} characters)"
        
        return True, ""
    
    def _set_ui_busy(self, busy: bool):
        """Set UI to busy/idle state"""
        state = "disabled" if busy else "normal"
        self.send_button.configure(state=state, text="..." if busy else "Send")
        self.input_entry.configure(state=state)
        
        if busy:
            self.send_button.configure(fg_color="gray")
        else:
            self.send_button.configure(fg_color=["#3B8ED0", "#1F6AA5"])
    
    def _show_error(self, error_message: str):
        """Display error message in chat"""
        error_html = self.formatter.create_message_html("Error", error_message, is_error=True)
        self.append_to_history(error_html)
        self.logger.error(f"UI Error: {error_message}")
    
    def on_send(self, event=None):
        """Handle send button click"""
        # Get and validate message
        user_message = self.input_entry.get("1.0", "end-1c").strip()
        
        is_valid, error_msg = self._validate_message(user_message)
        if not is_valid:
            if error_msg != "Message cannot be empty":  # Don't show error for empty
                self._show_error(error_msg)
            return
        
        # Check agent availability
        if not self.agent:
            self._show_error("Agent is not available. Please restart the application.")
            return
        
        self.logger.info(f"User query: {user_message[:100]}...")
        
        # Clear input
        self.input_entry.delete("1.0", "end")
        self._auto_resize_textbox()
        
        # Set UI to busy
        self._set_ui_busy(True)
        
        # Display user message
        user_html = self.formatter.create_message_html("You", user_message)
        self.append_to_history(user_html)
        
        # Prepare for streaming response
        with self.stream_lock:
            self.stream_count += 1
            self.current_stream_id = f"agent_response_{self.stream_count}"
            self.current_stream_content = ""
            self.stream_is_active = True
        
        # Show loading state
        self.append_to_history("<i>Thinking...</i>", self.current_stream_id)
        
        # Handle attachment
        image_data = None
        if self.has_attachment and hasattr(self.agent, 'pending_image_data'):
            image_data = self.agent.pending_image_data
            self.append_to_history("<i>(Screenshot attached to this message)</i>")
            self.after(0, self._hide_attachment_label)
        
        # Publish query event
        try:
            self.publish_async_event(
                "AGENT_EVENT.QUERY_RECEIVED",
                user_message=user_message,
                image_data=image_data
            )
        except Exception as e:
            self._show_error(f"Failed to send message: {str(e)}")
            self._set_ui_busy(False)
    
    def on_response_chunk(self, chunk: str):
        """Handle streaming response chunks"""
        with self.stream_lock:
            if not self.stream_is_active:
                return
            
            self.current_stream_content += chunk
            stream_content = self.current_stream_content
        
        # Batch UI updates
        if not self.ui_update_pending:
            self.ui_update_pending = True
            self.after(UIConstants.UI_UPDATE_BATCH_MS, self._update_stream_display, stream_content)
    
    def _update_stream_display(self, content: str):
        """Update streaming display (batched)"""
        
        # --- NEW FIX ---
        # Check if the stream has been completed by on_request_complete
        # while this batched update was waiting in the queue.
        with self.stream_lock:
            if not self.stream_is_active:
                self.ui_update_pending = False # We still clear the flag
                return # Do NOT update the UI with this stale chunk
        # --- END FIX ---

        self.ui_update_pending = False
        html_chunk = self.formatter.create_message_html("Agent", content)
        self.append_to_history(html_chunk, self.current_stream_id)
    
    def on_request_complete(self, full_response: str):
        """Handle request completion"""
        with self.stream_lock:
            if not self.stream_is_active:
                return # Already handled or cancelled
            
            # This is the flag that the new fix in _update_stream_display
            # will check.
            self.stream_is_active = False
        
        # Re-enable UI
        self.after(0, self._set_ui_busy, False)
        
        # This part is crucial: always render the final, full_response
        # to overwrite any partial chunks.
        self.logger.debug("Rendering final complete response.")
        final_html = self.formatter.create_message_html("Agent", full_response)
        
        # Schedule the final update to run on the main thread
        self.after(0, self.append_to_history, final_html, self.current_stream_id)
        
        # Clear the temporary stream content
        with self.stream_lock:
            self.current_stream_content = ""
    
    def append_to_history(self, html_content: str, element_id: Optional[str] = None):
        """Append or update message in chat history"""
        # Capture current scroll position before updating content
        saved_top = 0.0
        was_at_bottom = True
        try:
            canvas = self.chat_history_frame._parent_canvas
            if canvas:
                y0, y1 = canvas.yview()
                saved_top = y0
                # consider near-bottom if bottom edge is within 5%
                was_at_bottom = y1 > 0.95 or (y0, y1) == (0.0, 1.0)
        except Exception:
            pass

        # Update or add message
        if element_id:
            updated = False
            for msg in self.chat_messages:
                if msg.get("id") == element_id:
                    msg["html"] = html_content
                    updated = True
                    break
            
            if not updated:
                self.chat_messages.append({"id": element_id, "html": html_content})
        else:
            self.chat_messages.append({"id": None, "html": html_content})
        
        # Build complete HTML
        full_html_body = "<body>"
        for msg in self.chat_messages:
            wrapper_style = self.formatter.STYLE_WRAPPER
            if msg.get("id"):
                full_html_body += f'<div id="{msg["id"]}" style="{wrapper_style}">{msg["html"]}</div>'
            else:
                full_html_body += f'<div style="{wrapper_style}">{msg["html"]}</div>'
        full_html_body += "</body>"
        
        # Apply styles and render
        styled_html = self.formatter.apply_inline_styles(full_html_body)
        self.chat_history.set_html(styled_html)

        # Always scroll to the bottom after a delay
        self.after(100, self._force_scroll_to_bottom)
    
    def _scroll_to_bottom(self):
        """Scroll chat to bottom only if user is already at the bottom"""
        # --- MODIFIED: Implemented smart scrolling ---
        try:
            self.chat_history_frame.update_idletasks()
            canvas = self.chat_history_frame._parent_canvas
            if canvas:
                scroll_pos = canvas.yview()
                # scroll_pos[1] is the position of the bottom of the visible area
                # (0.0 at top, 1.0 at bottom)
                is_at_bottom = scroll_pos[1] > 0.95 
                
                # Handle case where canvas is not yet scrollable (e.g., empty)
                if scroll_pos == (0.0, 1.0):
                    is_at_bottom = True
                    
                if is_at_bottom:
                    canvas.yview_moveto(1.0)
        except Exception as e:
            self.logger.debug(f"Scroll error: {e}")

    def _force_scroll_to_bottom(self):
        """Forces the chat to scroll to the bottom."""
        try:
            self.chat_history_frame.update_idletasks()
            canvas = self.chat_history_frame._parent_canvas
            if canvas:
                canvas.yview_moveto(1.0)
        except Exception as e:
            self.logger.debug(f"Force scroll to bottom error: {e}")
    
    def on_new_chat(self, event=None):
        """Start a new chat session"""
        self.logger.info("New chat requested by user")
        self.clear_chat_ui()
        self.publish_async_event("AGENT_EVENT.CLEAR_CONTEXT")
        self.append_to_history("<i>Started new conversation</i>")
    
    def on_clear_chat(self, event=None):
        """Clear chat history"""
        self.logger.info("Clear chat requested by user")
        self.clear_chat_ui()
        self.publish_async_event("AGENT_EVENT.CLEAR_CONTEXT")
    
    def on_context_cleared_externally(self, *args):
        """Handle external context clear"""
        self.after(0, self.clear_chat_ui)
    
    def clear_chat_ui(self):
        """Clear chat UI elements"""
        self.logger.info("Clearing chat UI")
        self.chat_messages = []
        self.chat_history.set_html("<body></body>")
        self._hide_attachment_label()
        
        # Reset stream state
        with self.stream_lock:
            self.stream_is_active = False
            self.current_stream_content = ""
    
    def _on_window_move(self, event):
        """Track window geometry changes"""
        self.last_geometry = self.geometry()
    
    def publish_async_event(self, event_type: str, *args, **kwargs):
        """Publish event to async event loop"""
        async_loop = getattr(self.master, "async_loop", None)
        
        if not async_loop:
            error_msg = "Async event loop not available - cannot send message"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        try:
            coro = self.events.publish(event_type, *args, **kwargs)
            asyncio.run_coroutine_threadsafe(coro, async_loop)
        except Exception as e:
            self.logger.error(f"Failed to publish event {event_type}: {e}")
            raise
    
    def show(self):
        """Show the popup window"""
        ui_config = self.config.get_config("ui_config.json")
        geometry = ui_config.get("popup_window", {}).get(
            "geometry",
            UIConstants.DEFAULT_GEOMETRY
        )
        
        self.geometry(geometry)
        self.deiconify()
        self.lift()
        self.focus_force()
        self.input_entry.focus_set()
        self.is_visible = True
        
        # Show shortcuts hint
        self.shortcuts_label.grid(
            row=GridPosition.INPUT_ROW + 1, # --- MODIFIED ---
            column=0,
            columnspan=3,
            sticky="w",
            padx=UIConstants.PADDING_MEDIUM,
            pady=(0, UIConstants.PADDING_SMALL)
        )
        
        # Ensure grid is properly configured
        self.grid_rowconfigure(GridPosition.INPUT_ROW + 1, weight=0) # --- MODIFIED ---

    def hide(self):
        """Hide the popup window"""
        # Save geometry
        if self.last_geometry:
            ui_config = self.config.get_config("ui_config.json")
            ui_config.setdefault("popup_window", {})["geometry"] = self.last_geometry
            self.config.save_config("ui_config.json", ui_config)
            self.last_geometry = ""
        
        self.withdraw()
        self.is_visible = False

    def on_branch_changed(self, current_node_id: str):
        """Updates the UI when the conversation branch changes."""
        self.logger.debug(f"UI handling branch change to: {current_node_id}")
        self.after(0, self._update_branch_label, current_node_id)
    
    def _update_branch_label(self, node_id: str):
        """Helper to update label text and reload history from new branch."""
        # --- MODIFIED: Implemented TODO logic ---
        self.branch_label.configure(text=f"Current Branch: ...{node_id[-8:]}")
        self.logger.info(f"Reloading history for branch {node_id}")
        
        # Clear UI completely first
        self.clear_chat_ui()
        
        try:
            # Logic based on the original TODO comment
            if not hasattr(self.agent, 'context_manager') or \
               not callable(getattr(self.agent.context_manager, 'get_full_history', None)):
                self.logger.warning("Agent lacks 'context_manager.get_full_history' method.")
                self.append_to_history(f"<i>Switched to branch {node_id[-8:]}. (History reload not supported)</i>")
                return

            # This assumes get_full_history() returns history for the *current* node
            full_history = self.agent.context_manager.get_full_history() 
            
            if not full_history:
                self.append_to_history(f"<i>Switched to new/empty branch {node_id[-8:]}</i>")
                return

            # Re-populate the chat_messages list
            temp_messages = []
            for message in full_history:
                # Assuming format {'role': '...', 'content': '...'}
                role = message.get('role')
                content = message.get('content')
                
                if not role or content is None:
                    self.logger.warning(f"Skipping malformed history message: {message}")
                    continue
                
                if role == "system": # Don't show system messages
                    continue
                    
                label = "Agent"
                if role == "user":
                    label = "You"
                
                message_html = self.formatter.create_message_html(label, content)
                temp_messages.append({"id": None, "html": message_html})
            
            # Replace the (empty) chat_messages with the new history
            self.chat_messages = temp_messages
            
            # Manually trigger a render (copying logic from append_to_history)
            full_html_body = "<body>"
            for msg in self.chat_messages:
                wrapper_style = self.formatter.STYLE_WRAPPER
                if msg.get("id"):
                    full_html_body += f'<div id="{msg["id"]}" style="{wrapper_style}">{msg["html"]}</div>'
                else:
                    full_html_body += f'<div style="{wrapper_style}">{msg["html"]}</div>'
            full_html_body += "</body>"
            styled_html = self.formatter.apply_inline_styles(full_html_body)
            self.chat_history.set_html(styled_html)
            self.after_idle(self._scroll_to_bottom)

            # Add a final status message
            self.append_to_history(f"<i>Reloaded branch {node_id[-8:]}</i>")
            
        except Exception as e:
            self.logger.error(f"Failed to reload history for branch {node_id}: {e}")
            self.clear_chat_ui() # Clear again on failure
            self._show_error(f"Failed to reload history: {e}")