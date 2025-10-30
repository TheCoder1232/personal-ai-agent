# file: core/context/context_pruner.py

import logging
from typing import List, Dict, Any

class ContextPruner:
    """
    Handles logic for pruning a list of messages (a branch)
    before sending it to the LLM.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    def update_config(self, config: Dict[str, Any]):
        self.config = config
        self.logger.info("ContextPruner config updated.")

    def prune(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prunes the given message list based on the configured strategy.
        """
        strategy = self.config.get("pruning_strategy", "fifo")
        
        if strategy == "fifo":
            return self._prune_fifo(messages)
        # TODO: Add token-based or summary-based pruning
        else:
            self.logger.warning(f"Unknown pruning strategy '{strategy}'. Defaulting to 'fifo'.")
            return self._prune_fifo(messages)

    def _prune_fifo(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prunes messages using a simple First-In, First-Out (FIFO) queue
        based on max_messages.
        """
        max_messages = self.config.get("max_messages", 50)
        
        if len(messages) <= max_messages:
            return messages
            
        # Keep the most recent 'max_messages'
        pruned_list = messages[-max_messages:]
        
        self.logger.debug(f"Pruned conversation from {len(messages)} to {len(pruned_list)} messages (FIFO).")
        
        # TODO: Future enhancement: check for a system message at messages[0]
        # and ensure it's preserved.
        
        return pruned_list