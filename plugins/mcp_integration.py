# file: plugins/mcp_integration.py

import logging
import mcp
import asyncio
from plugins import PluginBase
from core.service_locator import ServiceLocator
from core.event_dispatcher import EventDispatcher
from core.command_executor import CommandExecutor
from utils.config_loader import ConfigLoader
from typing import Dict, Any, Optional

class MCPIntegrationPlugin(PluginBase):
    """
    Manages connections to MCP servers and executes tools.
    """
    def __init__(self, service_locator: ServiceLocator):
        super().__init__(service_locator)
        self.events: EventDispatcher = self.locator.resolve("event_dispatcher")
        self.config: ConfigLoader = self.locator.resolve("config_loader")
        self.executor: CommandExecutor = self.locator.resolve("command_executor")
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.servers: Dict[str, Any] = {} # To store server configs
        self.tool_registry: Dict[str, Any] = {} # To store discovered tools
        self.pending_tool_call: Optional[Dict] = None # For approval flow

    def get_metadata(self):
        return {
            "name": "MCPIntegration",
            "version": "1.0.0",
            "description": "Connects to and manages MCP tool servers."
        }

    def initialize(self):
        self.logger.info("MCPIntegrationPlugin initializing...")
        self.events.subscribe("AGENT_EVENT.TOOL_REQUESTED", self.on_tool_requested)
        self.events.subscribe("TOOL_EVENT.APPROVAL_RESULT", self.on_approval_result)
        self.events.subscribe("UI_EVENT.SETTINGS_CHANGED", self.load_servers)
        
        # We start server discovery in the background
        asyncio.create_task(self.discover_all_servers())

    async def load_servers(self):
        """Loads server definitions from mcp_config.json."""
        mcp_config = self.config.get_config("mcp_config.json")
        self.servers = {s["id"]: s for s in mcp_config.get("servers", []) if s.get("enabled", True)}
        self.logger.info(f"Loaded {len(self.servers)} enabled MCP servers.")
        
    async def discover_all_servers(self):
        """
        Connects to all enabled servers and lists their tools.
        """
        await self.load_servers()
        new_registry = {}
        self.logger.info("Starting MCP tool discovery...")
        
        for server_id, config in self.servers.items():
            command = config.get("command")
            args = config.get("args", [])
            
            if not command:
                self.logger.warning(f"Server '{server_id}' has no command. Skipping.")
                continue

            try:
                # Connect to MCP server and discover tools
                self.logger.debug(f"Discovering tools from: {command} {' '.join(args)}")
                tools = await self._discover_server_tools(command, args)
                
                for tool in tools:
                    tool_id = f"{server_id}::{tool.name}"
                    new_registry[tool_id] = {"server_id": server_id, "tool": tool}
                    self.logger.info(f"Discovered tool: {tool_id}")
                    
            except Exception as e:
                self.logger.error(f"Failed to discover tools from '{server_id}': {e}", exc_info=True)
                
        self.tool_registry = new_registry
        self.logger.info(f"MCP tool discovery complete. Found {len(self.tool_registry)} tools.")
        
        # Tell the agent about the tools (Phase 5 will use this)
        await self.events.publish("AGENT_EVENT.TOOLS_UPDATED", tools=self.tool_registry)

    async def _discover_server_tools(self, command: str, args: list) -> list:
        """
        Async helper to connect to MCP server and list tools.
        """
        # Use mcp.stdio_client for the current version
        server_params = mcp.StdioServerParameters(command=command, args=args)
        async with mcp.stdio_client(server_params) as (read, write):
            # Create a session from the streams
            session = mcp.ClientSession(read, write)
            await session.initialize()
            tools_result = await session.list_tools()
            return tools_result.tools

    async def on_tool_requested(self, tool_name: str, args: dict):
        """
        Called when the agent wants to use a tool.
        """
        self.logger.info(f"Agent requested tool: {tool_name} with args: {args}")
        
        if tool_name not in self.tool_registry:
            self.logger.error(f"Unknown tool '{tool_name}'. Not in registry.")
            await self.events.publish("TOOL_EVENT.EXECUTION_COMPLETE", tool_name=tool_name, success=False, output="Error: Unknown tool.")
            return

        # Store for approval
        self.pending_tool_call = {"tool_name": tool_name, "args": args}
        
        # Publish event for UI to show approval dialog
        await self.events.publish(
            "TOOL_EVENT.APPROVAL_NEEDED",
            tool_name=tool_name,
            args=args
        )

    async def on_approval_result(self, approved: bool):
        """
        Called when the user clicks 'Approve' or 'Reject' in the UI.
        """
        if not self.pending_tool_call:
            self.logger.warning("Received approval result with no pending tool call.")
            return
            
        call_details = self.pending_tool_call
        self.pending_tool_call = None
        tool_name = call_details["tool_name"]
        
        if not approved:
            self.logger.info(f"User rejected tool call: {tool_name}")
            await self.events.publish("TOOL_EVENT.EXECUTION_COMPLETE", tool_name=tool_name, success=False, output="User rejected the tool execution.")
            return

        self.logger.info(f"User approved tool call. Executing: {tool_name}")
        
        # Execute the tool
        # Note: This is a simplified execution. A real MCP client
        # would use session.call_tool(). For simplicity with your plan's
        # CommandExecutor, we are just re-launching the server process
        # for each call. This is inefficient but robust.
        
        # A true MCP client would keep the session open.
        # Let's pivot: We'll use the CommandExecutor to run the MCP
        # server as a command-line tool, which is simpler.
        
        tool_info = self.tool_registry.get(tool_name)
        if not tool_info:
            self.logger.error(f"Tool info not found for: {tool_name}")
            await self.events.publish("TOOL_EVENT.EXECUTION_COMPLETE", tool_name=tool_name, success=False, output="Error: Tool info not found.")
            return
            
        server_id = tool_info["server_id"]
        server_config = self.servers.get(server_id)
        
        # We need to format the tool call for the command line
        # e.g., `python -m mcp_server_filesystem call read_file --path /tmp/foo.txt`
        # This assumes MCP servers follow this CLI pattern.
        
        # For now, let's just log a "Not Implemented"
        self.logger.error("MCP tool execution logic is not fully implemented yet.")
        await self.events.publish(
            "TOOL_EVENT.EXECUTION_COMPLETE", 
            tool_name=tool_name, 
            success=False, 
            output="Tool execution via CommandExecutor is not yet implemented."
        )
        
        # TODO: Implement full mcp.client.stdio_client logic here
        # to call the tool, similar to _discover_server_tools.