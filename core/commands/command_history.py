# file: core/commands/command_history.py

import logging
from typing import List, Optional
from core.commands.base_command import BaseCommand

class CommandHistory:
    """
    Tracks a history of executed commands for undo/redo.
    """
    def __init__(self, max_size: int = 50):
        self.history: List[BaseCommand] = []
        self.max_size = max_size
        self.logger = logging.getLogger(self.__class__.__name__)

    def push(self, command: BaseCommand):
        """Adds an executed command to the history."""
        if not command.executed:
            self.logger.warning("Attempted to push a non-executed command to history.")
            return
            
        self.history.append(command)
        if len(self.history) > self.max_size:
            self.history.pop(0)
        self.logger.debug(f"Pushed command to history. Size: {len(self.history)}")

    def pop(self) -> Optional[BaseCommand]:
        """Removes and returns the last executed command."""
        if not self.history:
            return None
        return self.history.pop()

    async def undo_last(self) -> bool:
        """Undoes the last command in the history."""
        command = self.pop()
        if command:
            try:
                self.logger.info(f"Undoing command: {command.__class__.__name__}")
                await command.undo()
                return True
            except Exception as e:
                self.logger.error(f"Failed to undo command: {e}", exc_info=True)
                # Optionally, re-add to history if undo fails?
                # For now, we assume it's consumed.
                return False
        self.logger.info("No commands in history to undo.")
        return False