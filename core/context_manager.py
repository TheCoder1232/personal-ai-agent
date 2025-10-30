# file: core/context_manager.py

import logging
from typing import List, Dict, Any, Optional

from core.service_locator import locator
from utils.config_loader import ConfigLoader
# --- NEW IMPORTS ---
from core.context.conversation_tree import ConversationTree
from core.context.context_pruner import ContextPruner

class ContextManager:
    """
    Manages the conversation history (short-term memory) using a tree structure.
    Handles message storage, branching, and context pruning.
    """
    def __init__(self, locator):
        self.locator = locator
        self.config: ConfigLoader = self.locator.resolve("config_loader")
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # --- MODIFIED: Use ConversationTree and ContextPruner ---
        self.tree = ConversationTree()
        # Load initial empty config, will be populated by _load_config
        self.pruner = ContextPruner({})
        
        self._load_config()
        
        # Subscribe to config changes to reload settings
        events = self.locator.resolve("event_dispatcher")
        events.subscribe("UI_EVENT.SETTINGS_CHANGED", self._load_config)

    def _load_config(self):
        """Load context settings from context_config.json."""
        # --- MODIFIED: Load from new config file ---
        context_config = self.config.get_config("context_config.json")
        
        # Pass config to the pruner
        self.pruner.update_config(context_config)
        self.logger.info(f"ContextManager settings loaded: max_messages={context_config.get('max_messages')}")

    def add_message(self, role: str, content: Any):
        """Adds a new message to the current branch."""
        # LiteLLM standard roles are 'user' and 'assistant'
        if role not in ["user", "assistant", "tool"]: # Add 'tool' role
            self.logger.warning(f"Invalid message role '{role}'. Defaulting to 'user'.")
            role = "user" 
            
        # --- MODIFIED: Add to tree ---
        self.tree.add_message(role, content)
        # Pruning now happens on get_context()

    def get_context(self) -> List[Dict[str, Any]]:
        """
        Gets the current conversation context, pruned for the LLM.
        """
        # --- MODIFIED: Get from tree and prune ---
        # 1. Get the current branch from the tree
        current_branch = self.tree.get_current_branch()
        
        # 2. Prune the branch
        pruned_context = self.pruner.prune(current_branch)
        
        # TODO: Implement summarization logic here if needed
        # (based on summarize_threshold)
        
        return pruned_context
        
    def get_full_history(self) -> List[Dict[str, Any]]:
        """Returns the entire, untruncated history for the current branch."""
        # --- MODIFIED: Get full branch from tree ---
        return self.tree.get_current_branch()

    def clear(self):
        """Clears the conversation tree."""
        # --- MODIFIED: Clear tree ---
        self.tree.clear()
        self.logger.info("Conversation history cleared.")

    # --- NEW METHODS for Branching ---
    
    def create_branch_at(self, node_id: str) -> bool:
        """
        Sets the active node to a parent node, so the next
        add_message creates a new branch.
        """
        node = self.tree.create_branch_at(node_id)
        if node:
            # Publish event for UI to update
            self.locator.resolve("event_dispatcher").publish_sync(
                "CONTEXT_EVENT.BRANCH_CHANGED", 
                current_node_id=node.id
            )
            return True
        return False

    def switch_to_branch(self, node_id: str) -> bool:
        """
        Switches the active conversation to a different node (branch).
        """
        if self.tree.switch_to_node(node_id):
            self.locator.resolve("event_dispatcher").publish_sync(
                "CONTEXT_EVENT.BRANCH_CHANGED", 
                current_node_id=node_id
            )
            return True
        return False
        
    def get_branches(self) -> List[Any]:
        """
        Gets a representation of all branches for the UI.
        (This is a stub, UI would need a more complex structure)
        """
        return self.tree.get_all_branches()