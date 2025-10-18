# file: core/role_selector.py

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from core.service_locator import locator
from utils.config_loader import ConfigLoader

class RoleSelector:
    """
    Selects an appropriate agent role (system prompt) based on user query.
    
    Starts with keyword matching and will be upgraded to LLM-based
    classification.
    """
    def __init__(self, locator):
        self.locator = locator
        self.config: ConfigLoader = self.locator.resolve("config_loader")
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.roles_path = Path(__file__).parent.parent / "config" / "prompts" / "roles.json"
        self.roles: List[Dict[str, Any]] = []
        self.default_role: Dict[str, Any] = {}
        self.load_roles()

    def load_roles(self):
        """Loads role definitions from roles.json."""
        try:
            with open(self.roles_path, 'r', encoding='utf-8') as f:
                roles_config = json.load(f)
            
            self.roles = roles_config.get("roles", [])
            default_id = roles_config.get("default_role_id", "general")
            
            self.default_role = next(
                (r for r in self.roles if r["id"] == default_id), 
                self.roles[0] # Fallback to first role
            )
            
            if not self.default_role:
                 self.logger.error("No roles loaded. Roles.json might be empty.")
                 
            self.logger.info(f"Loaded {len(self.roles)} roles. Default is '{self.default_role['id']}'.")
            
        except FileNotFoundError:
            self.logger.error(f"roles.json not found at {self.roles_path}")
        except Exception as e:
            self.logger.error(f"Failed to load roles: {e}", exc_info=True)

    def select_role(self, user_query: str, current_role_id: Optional[str] = None) -> Tuple[str, str]:
        """
        Selects a role ID and system prompt for the query.
        
        Args:
            user_query (str): The new query from the user.
            current_role_id (str): The ID of the role used for the
                                     last turn, if any.
                                     
        Returns:
            Tuple[str, str]: (role_id, system_prompt)
        """
        
        # TODO: Implement LLM-based classification as per plan
        # 1. Check if current_role_id is None (new conversation)
        # 2. If new, call a fast LLM (Gemini Flash) with classification.json prompt
        # 3. Cache the result for the conversation
        
        # --- Simple Keyword-based selection (for now) ---
        
        # If we are already in a conversation, stick with that role.
        if current_role_id:
            role = next((r for r in self.roles if r["id"] == current_role_id), self.default_role)
            return role["id"], role["system_prompt"]
            
        # If it's a new conversation, try to match keywords
        query_lower = user_query.lower()
        for role in self.roles:
            for keyword in role.get("keywords", []):
                if keyword in query_lower:
                    self.logger.info(f"Role selected by keyword '{keyword}': {role['id']}")
                    return role["id"], role["system_prompt"]
                    
        # If no keywords match, use default
        self.logger.info("No keywords matched. Using default role.")
        return self.default_role["id"], self.default_role["system_prompt"]