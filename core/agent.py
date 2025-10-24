# file: core/agent.py

import logging
import asyncio
from typing import Optional
from core.service_locator import locator
from core.event_dispatcher import EventDispatcher
from core.api_manager import ApiManager
from core.context_manager import ContextManager
from core.role_selector import RoleSelector
from typing import Any

class Agent:
    """
    The core agent class.
    
    Orchestrates RoleSelector, ContextManager, and ApiManager
    to process user queries and generate responses.
    """
    def __init__(self, locator):
        self.locator = locator
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Resolve dependencies
        self.events: EventDispatcher = self.locator.resolve("event_dispatcher")
        self.api_manager: ApiManager = self.locator.resolve("api_manager")
        self.context_manager: ContextManager = self.locator.resolve("context_manager")
        self.role_selector: RoleSelector = self.locator.resolve("role_selector")
        
        self.current_role_id: Optional[str] = None
        
        # --- FIX: Add this line to initialize the attribute ---
        self.pending_image_data: Optional[str] = None

        # Subscribe to the event from the UI
        self.events.subscribe("AGENT_EVENT.QUERY_RECEIVED", self.process_query)
        self.events.subscribe("AGENT_EVENT.CLEAR_CONTEXT", self.on_clear_context)

        # --- NEW FOR PHASE 4 ---
        self.events.subscribe("PLUGIN_EVENT.SCREEN_CAPTURED", self.on_screen_captured)
    
    async def on_screen_captured(self, image_data: str, format: str):
        """
        Receives captured image data from the plugin and stores it
        for the *next* query.
        """
        if format == "base64":
            self.logger.info("Received screen capture data. Storing for next query.")
            self.pending_image_data = image_data
        else:
            self.logger.warning(f"Received screen capture in unknown format: {format}")

    async def on_clear_context(self):
        """Event handler to clear conversation history."""
        self.context_manager.clear()
        self.current_role_id = None
        self.pending_image_data = None
        self.logger.info("Agent context cleared.")

    async def process_query(self, user_message: str, image_data: Optional[str] = None):
        """
        Main method to process a user's query.
        This is the full request-response flow.
        """
        self.logger.info(f"Processing query: '{user_message[:50]}...'")

        # --- FIX: Check for image and format message ---
        
        # The 'image_data' argument is already passed from popup_window.py
        # We just need to consume the pending image in the agent's state
        # so it's not used twice.
        if image_data:
            self.pending_image_data = None # Consume the pending image
            self.logger.info("Query includes image data, formatting for multimodal.")
            
        try:
            # 1. Format the message content
            message_content: Any # Can be str or list
            
            if image_data:
                # This is the multimodal format from your TODO
                message_content = [
                    {"type": "text", "text": user_message},
                    {
                        "type": "image_url",
                        "image_url": {
                            # Prepend the data URI scheme, which is required
                            "url": f"data:image/jpeg;base64,{image_data}" 
                        }
                    }
                ]
            else:
                # This is a standard text-only message
                message_content = user_message

            # 2. Add the (potentially complex) message to context
            self.context_manager.add_message("user", message_content)

            # 2. Select role (and get system prompt)
            # We pass the current_role_id to maintain conversational context
            role_id, system_prompt = self.role_selector.select_role(
                user_message, 
                self.current_role_id
            )
            self.current_role_id = role_id
            await self.events.publish("API_EVENT.ROLE_SELECTED", role_id=role_id)
            
            # 3. Get context (history)
            messages = self.context_manager.get_context()
            

            # 4. Stream response from API
            full_response = ""
            
            # The chat_stream function is synchronous (a generator),
            # but it yields chunks quickly. We run it in a separate
            # thread to avoid blocking the asyncio loop.
            stream_generator = await asyncio.to_thread(
                self.api_manager.chat_stream,  # <--- THIS IS THE KEY
                messages=messages,
                system_prompt=system_prompt
            )

            for chunk in stream_generator:
                full_response += chunk
                # Publish chunks for the UI to render in real-time
                await self.events.publish("API_EVENT.RESPONSE_CHUNK", chunk=chunk)
            
            # 5. Add full model response to context
            self.context_manager.add_message("assistant", full_response)
            
            # 6. Publish final response
            self.logger.info(f"Full response generated ({len(full_response)} chars).")
            await self.events.publish("API_EVENT.REQUEST_COMPLETE", full_response=full_response)
            
            # TODO: Parse for tool requests here
            # 4a. Parse response for tool calls
            # 4b. Emit TOOL_EVENT.EXECUTION_REQUESTED

        except Exception as e:
            self.logger.error(f"Error in agent.process_query: {e}", exc_info=True)
            error_message = f"An internal error occurred: {e}"
            await self.events.publish("API_EVENT.REQUEST_COMPLETE", full_response=error_message)
            await self.events.publish("NOTIFICATION_EVENT.ERROR", title="Agent Error", message=str(e))