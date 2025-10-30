# file: core/command_executor.py

import logging
import asyncio
from typing import Tuple, Any

from core.service_locator import locator
from core.event_dispatcher import EventDispatcher
# --- NEW IMPORTS ---
from core.commands.base_command import BaseCommand
from core.commands.command_history import CommandHistory
from utils.config_loader import ConfigLoader

class CommandExecutor:
    """
    Implements the Command Pattern's "Invoker".
    It accepts Command objects, executes them, and keeps a history.
    """
    def __init__(self, locator):
        self.locator = locator
        self.events: EventDispatcher = self.locator.resolve("event_dispatcher")
        self.config: ConfigLoader = self.locator.resolve("config_loader")
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # --- NEW: Load config and init history ---
        cmd_config = self.config.get_config("commands_config.json")
        max_history = cmd_config.get("max_history", 50)
        self.history = CommandHistory(max_size=max_history)
        self.logger.info(f"CommandExecutor initialized with history size {max_history}")

    async def execute(self, command: BaseCommand) -> Tuple[bool, Any]:
        """
        Executes a Command object.
        
        Args:
            command (BaseCommand): The command to execute.

        Returns:
            Tuple[bool, Any]: (is_success, result)
            'result' will be command.result if successful, or error string if failed.
        """
        command_name = command.__class__.__name__
        self.logger.info(f"Executing command: {command_name}")
        
        # Event publishing is now delegated to the command itself
        # or the caller (e.g., mcp_integration)
        
        try:
            # --- MODIFIED: Delegate execution to command object ---
            await command.execute()
            
            if command.executed:
                self.logger.info(f"Command {command_name} success.")
                self.history.push(command) # Add to history only if successful
                return True, command.result
            else:
                self.logger.error(f"Command {command_name} failed during execution. Result: {command.result}")
                return False, command.result

        except Exception as e:
            self.logger.error(f"Command execution error: {e}", exc_info=True)
            return False, f"An unexpected error occurred: {e}"

    async def undo(self) -> bool:
        """
        Undoes the last executed command.
        """
        return await self.history.undo_last()