# file: core/command_executor.py

import logging
import asyncio
import subprocess
from typing import Tuple, Optional

from core.service_locator import locator
from core.event_dispatcher import EventDispatcher

class CommandExecutor:
    """
    Safely executes shell commands in a non-blocking way.
    Runs commands in a separate process with a timeout.
    """
    def __init__(self, locator):
        self.locator = locator
        self.events: EventDispatcher = self.locator.resolve("event_dispatcher")
        self.logger = logging.getLogger(self.__class__.__name__)

    async def execute(self, command: str, args: Optional[list] = None, timeout: int = 30) -> Tuple[bool, str]:
        """
        Executes a command in a subprocess with a timeout.
        
        Args:
            command (str): The command or program to run (e.g., "python", "ls").
            args (list): A list of string arguments for the command (e.g., ["-m", "mcp_server"]).
            timeout (int): Max seconds to let the command run.

        Returns:
            Tuple[bool, str]: (is_success, output)
            'output' will be stdout if successful, or stderr if failed.
        """
        full_command = [command] + (args or [])
        cmd_str = " ".join(full_command)
        self.logger.info(f"Executing command: {cmd_str} with timeout {timeout}s")
        
        await self.events.publish("TOOL_EVENT.STARTED", command=cmd_str)
        
        try:
            # asyncio.create_subprocess_exec is the modern, async way to do this
            proc = await asyncio.create_subprocess_exec(
                *full_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Wait for the process to terminate or timeout
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            
            stdout = stdout_bytes.decode('utf-8').strip()
            stderr = stderr_bytes.decode('utf-8').strip()

            if proc.returncode == 0:
                self.logger.info(f"Command success: {cmd_str}")
                await self.events.publish("TOOL_EVENT.OUTPUT", output=stdout)
                await self.events.publish("TOOL_EVENT.COMPLETE", command=cmd_str, success=True, output=stdout)
                return True, stdout
            else:
                self.logger.error(f"Command failed (code {proc.returncode}): {cmd_str} | Error: {stderr}")
                await self.events.publish("TOOL_EVENT.COMPLETE", command=cmd_str, success=False, output=stderr)
                return False, stderr

        except asyncio.TimeoutError:
            self.logger.error(f"Command timed out: {cmd_str}")
            try:
                proc.kill()
            except ProcessLookupError:
                pass # Process already finished
            await self.events.publish("TOOL_EVENT.TIMEOUT", command=cmd_str)
            return False, "Command timed out."
        
        except FileNotFoundError:
            self.logger.error(f"Command not found: {command}")
            await self.events.publish("TOOL_EVENT.COMPLETE", command=cmd_str, success=False, output="Command not found")
            return False, f"Error: Command '{command}' not found. Is it in your PATH?"
            
        except Exception as e:
            self.logger.error(f"Command execution error: {e}", exc_info=True)
            await self.events.publish("TOOL_EVENT.COMPLETE", command=cmd_str, success=False, output=str(e))
            return False, f"An unexpected error occurred: {e}"