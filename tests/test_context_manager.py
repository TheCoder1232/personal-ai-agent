# file: tests/test_context_manager.py

import pytest
from unittest.mock import MagicMock

from core.context_manager import ContextManager

@pytest.fixture
def context_manager(mock_service_locator):
    """Initializes ContextManager with a mocked locator."""
    # Configure the mock config loader for ContextManager
    mock_service_locator.mock_config_loader.get_config.return_value = {
        "max_messages": 3,
        "pruning_strategy": "fifo"
    }
    return ContextManager(mock_service_locator)

def test_add_message(context_manager):
    """Tests adding a single message."""
    context_manager.add_message("user", "Hello")
    
    history = context_manager.get_full_history()
    assert len(history) == 1
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello"

def test_context_pruning(context_manager):
    """Tests if the context is pruned based on max_messages."""
    context_manager.add_message("user", "Message 1")
    context_manager.add_message("assistant", "Message 2")
    context_manager.add_message("user", "Message 3")
    context_manager.add_message("assistant", "Message 4")
    
    # Full history should have all messages
    assert len(context_manager.get_full_history()) == 4
    
    # Pruned context should respect max_messages
    pruned_context = context_manager.get_context()
    assert len(pruned_context) == 3
    assert pruned_context[0]["content"] == "Message 2"

def test_clear_history(context_manager):
    """Tests clearing the conversation history."""
    context_manager.add_message("user", "A message")
    context_manager.clear()
    
    assert len(context_manager.get_full_history()) == 0

def test_branching_and_switching(context_manager):
    """Tests creating and switching between conversation branches."""
    # Main branch
    context_manager.add_message("user", "A")
    context_manager.add_message("assistant", "B")
    node_id_to_branch_from = context_manager.tree.current_node.id

    # Create a new branch from node "A"
    assert context_manager.create_branch_at(node_id_to_branch_from)
    context_manager.add_message("user", "C")
    
    # Check current branch
    branch1 = context_manager.get_full_history()
    assert len(branch1) == 3
    assert branch1[-1]["content"] == "C"
    
    # Switch back to the original branch's leaf node
    leaf_node_main_branch = context_manager.tree.nodes_by_id[node_id_to_branch_from]
    assert context_manager.switch_to_branch(leaf_node_main_branch.id)
    
    # Add a message to continue the main branch
    context_manager.add_message("user", "D")
    
    # Check the main branch again
    main_branch_continued = context_manager.get_full_history()
    assert len(main_branch_continued) == 3
    assert main_branch_continued[-1]["content"] == "D"
    
    # Verify the other branch is still intact
    assert context_manager.switch_to_branch(branch1[-1]['id'])
    assert context_manager.get_full_history()[-1]['content'] == 'C'
