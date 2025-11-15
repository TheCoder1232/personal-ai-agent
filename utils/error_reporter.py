# file: utils/error_reporter.py

import abc
import aiofiles
import asyncio
import json
import datetime
import logging
from pathlib import Path
from typing import Dict, Any, Protocol

# Get a logger for this module
logger = logging.getLogger(__name__)

class BaseErrorReporter(abc.ABC):
    """
    Abstract base class for error reporting strategies.
    """
    
    @abc.abstractmethod
    async def report_issue(self, pattern_hash: str, error_details: Dict[str, Any]):
        """
        Reports a new or recurring issue.

        Args:
            pattern_hash: A unique hash identifying the error pattern.
            error_details: A dictionary containing details about the error.
        """
        pass

class JsonFileErrorReporter(BaseErrorReporter):
    """
    An error reporter that writes issue details to a JSON file.
    
    This implementation will create/update a JSON file for each unique
    error pattern hash.
    """
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock() # Lock for file I/O operations

    async def report_issue(self, pattern_hash: str, error_details: Dict[str, Any]):
        """
        Writes the error report to a file named <pattern_hash>.json.
        If the file already exists, it updates the count and last_updated timestamp.
        """
        report_file = self.output_dir / f"{pattern_hash}.json"
        now_iso = datetime.datetime.utcnow().isoformat()
        
        async with self._lock:
            report_data = {}
            if report_file.exists():
                try:
                    async with aiofiles.open(report_file, 'r', encoding='utf-8') as f:
                        report_data = json.loads(await f.read())
                except (IOError, json.JSONDecodeError) as e:
                    logger.warning(f"Could not read existing error report {report_file}: {e}. Overwriting.")
                    report_data = {}
            
            # Update data
            report_data["pattern_hash"] = pattern_hash
            report_data.setdefault("first_reported_utc", now_iso)
            report_data["last_reported_utc"] = now_iso
            report_data["total_occurrences"] = report_data.get("total_occurrences", 0) + error_details.get("count_in_timespan", 1)
            report_data["last_report_details"] = error_details
            
            # Write data back to file
            try:
                async with aiofiles.open(report_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(report_data, indent=2))
                logger.info(f"Error report written/updated: {report_file}")
            except IOError as e:
                logger.error(f"Failed to write error report to {report_file}: {e}")

# Type alias for the ConfigLoader
class ConfigLoader(Protocol):
    def get_config(self, config_name: str) -> dict: ...
    def get_data_dir(self) -> Path: ...

def get_reporter(config_loader: ConfigLoader) -> BaseErrorReporter:
    """
    Factory function to create the appropriate error reporter based on config.
    """
    report_config = config_loader.get_config("error_analytics_config.json").get("reporting", {})
    reporter_type = report_config.get("type", "json_file")
    
    data_dir = config_loader.get_data_dir()
    
    if reporter_type == "json_file":
        relative_dir = report_config.get("output_directory", "reports/errors")
        output_dir = data_dir / relative_dir
        return JsonFileErrorReporter(output_dir)
    # --- Future Extension ---
    # elif reporter_type == "github":
    #     return GitHubIssueReporter(config)
    else:
        logger.error(f"Unknown error reporter type: {reporter_type}. Defaulting to no-op.")
        # Return a dummy reporter that does nothing
        class NoOpReporter(BaseErrorReporter):
            async def report_issue(self, *args, **kwargs):
                pass
        return NoOpReporter()