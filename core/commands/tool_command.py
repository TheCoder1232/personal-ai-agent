# file: core/commands/tool_command.py

import logging
import mcp
from typing import Dict, Any
from core.commands.base_command import BaseCommand

class ToolCommand(BaseCommand):
    """
    A command object that encapsulates the execution of an MCP tool.
    """
    def __init__(self, tool_name: str, tool_args: Dict[str, Any], server_config: Dict[str, Any]):
        super().__init__()
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.server_config = server_config
        self.logger = logging.getLogger(self.__class__.__name__)

    async def execute(self):
        """
        Executes the MCP tool call using mcp.stdio_client.
        """
        self.logger.info(f"Executing ToolCommand: {self.tool_name} with args {self.tool_args}")
        
        command = self.server_config.get("command")
        args = self.server_config.get("args", [])
        
        if not command:
            self.logger.error(f"No command found for server: {self.server_config.get('id')}")
            self.result = "Error: Server configuration is missing 'command'."
            self.executed = False # Mark as failed
            return

        try:
            # Use mcp.stdio_client to connect and call the tool
            server_params = mcp.StdioServerParameters(command=command, args=args)
            async with mcp.stdio_client(server_params) as (read, write):
                session = mcp.ClientSession(read, write)
                await session.initialize()
                
                # Extract the actual tool name (e.g., 'read_file' from 'filesystem::read_file')
                _, mcp_tool_name = self.tool_name.split("::", 1)
                
                self.logger.debug(f"Calling MCP tool: {mcp_tool_name} with params: {self.tool_args}")
                
                call_result = await session.call_tool(mcp_tool_name, self.tool_args)
                
                # The result is a ToolCallResult object
                # We'll just return the payload
                self.result = call_result.payload
                self.executed = True
                self.logger.info(f"Tool {self.tool_name} executed successfully.")

        except Exception as e:
            self.logger.error(f"Failed to execute tool '{self.tool_name}': {e}", exc_info=True)
            self.result = f"Error executing tool '{self.tool_name}': {e}"
            self.executed = False # Mark as failed

    async def undo(self):
        """
        Undo functionality is not implemented for tool calls.
        This would require a complex compensating transaction.
        """
        self.logger.warning(f"Undo not implemented for ToolCommand: {self.tool_name}")
        pass