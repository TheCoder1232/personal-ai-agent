# file: core/context_manager.py

import logging
from typing import List, Dict, Tuple
from core.service_locator import locator
from utils.config_loader import ConfigLoader

class ContextManager:
    """
    Manages the conversation history (short-term memory).
    Handles message storage and future summarization.
    """
    def __init__(self, locator):
        self.locator = locator
        self.config: ConfigLoader = self.locator.resolve("config_loader")
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.history: List[Dict[str, str]] = []
        self._load_config()
        
        # Subscribe to config changes to reload settings
        events = self.locator.resolve("event_dispatcher")
        events.subscribe("UI_EVENT.SETTINGS_CHANGED", self._load_config)

    def _load_config(self):
        """Load context settings from system_config.json."""
        system_config = self.config.get_config("system_config.json")
        context_config = system_config.get("context", {})
        self.max_messages = context_config.get("max_messages", 50)
        self.summarize_threshold = context_config.get("summarize_threshold", 20)
        self.logger.info(f"ContextManager settings loaded: max_messages={self.max_messages}")

    def add_message(self, role: str, content: str):
        """Adds a new message to the history."""
        # Roles should be 'user' or 'model' (for Gemini/Ollama)
        if role not in ["user", "model"]:
            self.logger.warning(f"Invalid message role '{role}'. Defaulting to 'user'.")
            role = "user"
            
        self.history.append({"role": role, "content": content})
        self.enforce_limits()

    def get_context(self) -> List[Dict[str, str]]:
        """
        Gets the current conversation context.
        In the future, this will prepend a summary.
        """
        # TODO: Implement summarization
        # 1. Check if len(self.history) > self.summarize_threshold
        # 2. If so, call LLM to summarize self.history[:-self.summarize_threshold]
        # 3. Store summary
        # 4. Return [summary] + self.history[-self.summarize_threshold:]
        
        # For now, just return the truncated history
        return self.history

    def enforce_limits(self):
        """Enforces the max_messages limit."""
        if len(self.history) > self.max_messages:
            # Simple FIFO eviction
            self.history = self.history[-self.max_messages:]
            self.logger.debug(f"History truncated to {self.max_messages} messages.")
            
    def get_full_history(self) -> List[Dict[str, str]]:
        """Returns the entire, untruncated history."""
        return self.history

    def clear(self):
        """Clears the conversation history."""
        self.history = []
        self.logger.info("Conversation history cleared.")