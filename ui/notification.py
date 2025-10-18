# file: ui/notification.py

import logging
import asyncio
import customtkinter as ctk
from core.service_locator import locator
from core.event_dispatcher import EventDispatcher

class NotificationWindow(ctk.CTkToplevel):
    """
    A small, temporary window to display a notification.
    """
    def __init__(self, master, title, message):
        super().__init__(master)
        self.title(title)
        self.geometry("300x100")
        self.attributes("-topmost", True)
        
        # Position at bottom right of screen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.geometry(f"+{screen_w - 310}+{screen_h - 140}")
        
        self.protocol("WM_DELETE_WINDOW", self.close_notification)
        
        self.label = ctk.CTkLabel(self, text=message, wraplength=280)
        self.label.pack(padx=10, pady=10, expand=True, fill="both")
        
        # Auto-close after 5 seconds
        self.after(5000, self.close_notification)
        
    def close_notification(self):
        self.destroy()


class NotificationManager:
    """
    Listens for notification events and creates notification windows.
    """
    def __init__(self, app):
        self.app = app
        self.locator = locator
        self.events: EventDispatcher = self.locator.resolve("event_dispatcher")
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Subscribe to all notification events
        self.events.subscribe("NOTIFICATION_EVENT.INFO", self.show_info)
        self.events.subscribe("NOTIFICATION_EVENT.WARNING", self.show_warning)
        self.events.subscribe("NOTIFICATION_EVENT.ERROR", self.show_error)
        self.events.subscribe("TOOL_EVENT.APPROVAL_NEEDED", self.show_approval)
        
    def show_info(self, title: str, message: str):
        self.logger.info(f"Notification (Info): {title} - {message}")
        # Must create UI from the main thread
        self.app.after(0, self._create_notification, title, message)
        
    def show_warning(self, title: str, message: str):
        self.logger.warning(f"Notification (Warning): {title} - {message}")
        self.app.after(0, self._create_notification, title, message)
        
    def show_error(self, title: str, message: str):
        self.logger.error(f"Notification (Error): {title} - {message}")
        self.app.after(0, self._create_notification, title, message)
        
    def show_approval(self, tool_name: str, args: dict):
        """
        Shows a tool approval notification.
        This is a placeholder; a real one would have Approve/Reject buttons.
        """
        self.logger.info(f"Tool approval needed: {tool_name}")
        title = "Tool Approval Request"
        message = f"Allow agent to use tool '{tool_name}'?"
        self.app.after(0, self._create_notification, title, message)
        
        # TODO: Implement full approval logic with buttons
        # For now, we'll auto-approve for testing
        self.publish_async_event("TOOL_EVENT.APPROVAL_RESULT", approved=True)

    def _create_notification(self, title, message):
        """Internal method to create the window on the main thread."""
        NotificationWindow(self.app, title, message)
        
    def publish_async_event(self, event_type: str, *args, **kwargs):
        """Safely publishes an event to the asyncio loop from the UI thread."""
        async_loop = self.app.async_loop
        if not async_loop:
            self.logger.warning("Async loop not available. Cannot publish event.")
            return
        
        coro = self.events.publish(event_type, *args, **kwargs)
        asyncio.run_coroutine_threadsafe(coro, async_loop)