# file: core/context/conversation_tree.py

import logging
import uuid
from typing import List, Dict, Optional, Any

class Node:
    """A node in the conversation tree."""
    def __init__(self, message: Dict[str, Any], parent: Optional['Node'] = None):
        self.id: str = str(uuid.uuid4())
        self.message: Dict[str, Any] = message
        self.parent: Optional['Node'] = parent
        self.children: List['Node'] = []

    def add_child(self, message: Dict[str, Any]) -> 'Node':
        """Adds a child node to this node."""
        child = Node(message, parent=self)
        self.children.append(child)
        return child

    def __repr__(self):
        return f"Node(id={self.id}, role={self.message.get('role')})"

class ConversationTree:
    """Manages the conversation as a tree structure for branching."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        # Create a root node with a system message
        self.root: Node = Node({"role": "system", "content": "Conversation started."})
        self.current_node: Node = self.root
        self.nodes_by_id: Dict[str, Node] = {self.root.id: self.root}
        self.logger.info(f"ConversationTree initialized with root node {self.root.id}")

    def add_message(self, role: str, content: Any):
        """Adds a new message as a child of the current node."""
        message = {"role": role, "content": content}
        new_node = self.current_node.add_child(message)
        self.nodes_by_id[new_node.id] = new_node
        parent_id = new_node.parent.id if new_node.parent is not None else None
        self.current_node = new_node
        self.logger.debug(f"Added message node {new_node.id} to parent {parent_id}")

    def get_current_branch(self) -> List[Dict[str, Any]]:
        """Walks up the tree from the current node to get the history."""
        messages: List[Dict[str, Any]] = []
        node = self.current_node
        while node:
            # Don't include the dummy root message in the context
            if node.parent is not None: 
                message_with_id = node.message.copy()
                message_with_id['id'] = node.id # Add the node ID
                messages.append(message_with_id)
            node = node.parent
        
        # Messages are from new to old, so reverse them
        return messages[::-1]

    def switch_to_node(self, node_id: str) -> bool:
        """Sets the current node to a different node in the tree."""
        if node_id in self.nodes_by_id:
            self.current_node = self.nodes_by_id[node_id]
            self.logger.info(f"Switched context to branch at node {node_id}")
            return True
        else:
            self.logger.warning(f"Node ID {node_id} not found. Cannot switch context.")
            return False

    def create_branch_at(self, node_id: str) -> Optional[Node]:
        """
        Sets the current node to a specific parent, ready for a new
        message to create a new branch.
        """
        if node_id in self.nodes_by_id:
            self.current_node = self.nodes_by_id[node_id]
            self.logger.info(f"Ready to branch from node {node_id}. Next message will create new branch.")
            return self.current_node
        else:
            self.logger.warning(f"Node ID {node_id} not found. Cannot create branch.")
            return None

    def clear(self):
        """Resets the tree to a new root."""
        self.root = Node({"role": "system", "content": "Conversation started."})
        self.current_node = self.root
        self.nodes_by_id = {self.root.id: self.root}
        self.logger.info("Conversation tree cleared.")

    def get_all_branches(self) -> List[List[Node]]:
        """Returns all branches (lists of nodes) from root to leaf."""
        # This can be complex, implementing a simple version for now
        # that just shows leaf nodes.
        # TODO: Implement full branch traversal if needed for UI.
        leaf_nodes = [node for node in self.nodes_by_id.values() if not node.children]
        return [self._get_branch_for_node(leaf.id) for leaf in leaf_nodes]

    def _get_branch_for_node(self, node_id: str) -> List[Node]:
        """Helper to get a branch for any node ID."""
        branch = []
        node = self.nodes_by_id.get(node_id)
        while node:
            branch.append(node)
            node = node.parent
        return branch[::-1]