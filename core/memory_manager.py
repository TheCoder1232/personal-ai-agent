# file: core/memory_manager.py

import asyncio
import logging
import os
import psutil
from typing import Dict, Optional
from core.service_locator import ServiceLocator
from utils.config_loader import ConfigLoader
from core.event_dispatcher import EventDispatcher
from typing import Any

class MemoryManager:
    """
    Manages and monitors memory usage for the application.
    
    - Runs a background task to monitor overall process RSS memory.
    - Emits events if memory usage exceeds a configured threshold.
    - Allows components (like plugins) to be "tracked" for logging purposes.
    """
    
    def __init__(self, service_locator: ServiceLocator):
        self.locator = service_locator
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Injected services (resolved later)
        self.config_loader: ConfigLoader = self.locator.resolve("config_loader")
        self.event_dispatcher: EventDispatcher = self.locator.resolve("event_dispatcher")
        
        # Process monitoring
        self.process = psutil.Process(os.getpid())
        
        # Configuration
        self._load_config()

        self.tracked_components: Dict[str, Any] = {}
        self._monitor_task: Optional[asyncio.Task] = None

    def _load_config(self):
        """Loads configuration from the ConfigLoader."""
        config = self.config_loader.get_config("memory_config.json")
        self.enabled = config.get("enabled", True)
        self.threshold_mb = config.get("threshold_mb", 500)
        self.interval_sec = config.get("monitor_interval_sec", 60)
        log_level = config.get("log_level", "INFO")
        self.logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        
    def start_monitoring(self):
        """Starts the background memory monitoring task."""
        if not self.enabled:
            self.logger.info("Memory monitoring is disabled by config.")
            return

        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self.monitor_resource_usage())
            self.logger.info(f"Memory monitor started. Threshold: {self.threshold_mb}MB, Interval: {self.interval_sec}s")
        else:
            self.logger.warning("Monitoring task is already running.")

    async def stop_monitoring(self):
        """Stops the background monitoring task."""
        if self._monitor_task and not self._monitor_task.done():
            self.logger.info("Stopping memory monitor...")
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                self.logger.info("Memory monitor successfully stopped.")
            self._monitor_task = None

    async def monitor_resource_usage(self):
        """
        The background task loop that periodically checks memory usage.
        """
        try:
            while True:
                mem_info = self.process.memory_info()
                current_rss_mb = mem_info.rss / (1024 * 1024)
                
                self.logger.debug(f"Current process memory: {current_rss_mb:.2f} MB")
                
                if current_rss_mb > self.threshold_mb:
                    self.logger.warning(
                        f"Memory usage high: {current_rss_mb:.2f} MB. "
                        f"Exceeds threshold of {self.threshold_mb} MB."
                    )
                    await self.event_dispatcher.publish(
                        "MEMORY_EVENT.HIGH_USAGE",
                        current_mb=current_rss_mb,
                        threshold_mb=self.threshold_mb
                    )
                
                await asyncio.sleep(self.interval_sec)
        except asyncio.CancelledError:
            raise # Re-raise cancellation
        except Exception as e:
            self.logger.error(f"Memory monitoring loop crashed: {e}", exc_info=True)

    def track_component(self, component_name: str):
        """
        Registers a component for tracking.
        (Future-proofing: This could be expanded to track object sizes)
        """
        if component_name in self.tracked_components:
            self.logger.warning(f"Component '{component_name}' is already tracked.")
            return
            
        self.logger.debug(f"Tracking component: {component_name}")
        self.tracked_components[component_name] = {"status": "tracked"}

    def get_current_usage_mb(self) -> float:
        """Gets the current process RSS memory in megabytes."""
        return self.process.memory_info().rss / (1024 * 1024)