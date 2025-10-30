# file: core/commands/base_command.py

from abc import ABC, abstractmethod
from typing import Any

class BaseCommand(ABC):
    """
    Abstract base class for a command in the Command Pattern.
    """
    def __init__(self):
        self.executed: bool = False
        self.result: Any = None

    @abstractmethod
    async def execute(self):
        """
        Execute the command.
        This method should populate self.result and set self.executed = True.
        """
        pass

    @abstractmethod
    async def undo(self):
        """
        Reverse the effects of the execute method, if possible.
        """
        pass