# file: utils/logger.py

import logging
import sys
import os
import psutil
import asyncio
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Protocol
from core.error_analytics import ErrorAnalytics 

# --- ADDED: AnalyticsLogHandler ---
class AnalyticsLogHandler(logging.Handler):
    """
    A logging handler that forwards error records to the ErrorAnalytics service.
    """
    def __init__(self, analytics: ErrorAnalytics, level=logging.ERROR):
        super().__init__(level=level)
        self.analytics = analytics

    def emit(self, record: logging.LogRecord):
        """
        Emit a log record.
        """
        if record.exc_info:
            error = record.exc_info[1]
            if not error:
                if record.exc_info[0] is not None:
                    try:
                        error = record.exc_info[0]() 
                    except TypeError:
                        error = Exception(f"Log Error: {record.exc_info[0].__name__}")
                else:
                    return 
            
            context = {
                "log_message": record.getMessage(),
                "module": record.module,
                "funcName": record.funcName,
                "lineno": record.lineno,
            }
            
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    if not isinstance(error, Exception):
                        error = Exception(f"{type(error).__name__}: {error}")
                    asyncio.create_task(self.analytics.analyze_error(error, context))
            except RuntimeError:
                print(f"WARNING: Could not submit error to analytics. No running event loop. Error: {error}", file=sys.stderr)
# --- END ADDED SECTION ---


# --- MODIFIED: Protocol for ConfigLoader ---
# This provides type hints for the config_loader dependency
class ConfigLoader(Protocol):
    # The parameter name is changed from 'config_name' to 'filename'
    # to match the actual method signature in utils/config_loader.py
    def get_config(self, filename: str) -> dict: ... 
    def get_data_dir(self) -> Path: ...
# --- END MODIFIED SECTION ---


class MemoryLogFilter(logging.Filter):
    """
    Injects current process memory (RSS) into log records.
    """
    def __init__(self):
        super().__init__()
        try:
            self.process = psutil.Process(os.getpid())
        except psutil.NoSuchProcess:
            self.process = None 

    def filter(self, record):
        if self.process:
            try:
                mem_info = self.process.memory_info()
                record.mem_rss_mb = mem_info.rss / (1024 * 1024)
            except psutil.Error:
                record.mem_rss_mb = 0.0
        else:
            record.mem_rss_mb = 0.0
        return True


# --- MODIFIED: Function signature ---
def setup_logging(config_loader: ConfigLoader, analytics_service: Optional[ErrorAnalytics] = None):
# --- END MODIFIED SECTION ---
    """
    Configures the global logging system.
    """
    
    log_config = config_loader.get_config("system_config.json").get("logging", {})
    log_level_str = log_config.get("level", "INFO")
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    
    log_dir = config_loader.get_data_dir() / "logs" 
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "agent.log"
    
    log_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(mem_rss_mb)4.1fMB] - %(message)s (%(filename)s:%(lineno)d)"
    )
    
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    memory_filter = MemoryLogFilter()
    
    # --- Console Handler ---
    if not any(h.get_name() == "app_console_handler" for h in logger.handlers):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.set_name("app_console_handler")
        console_handler.setLevel(log_level)
        console_handler.setFormatter(log_format)
        console_handler.addFilter(memory_filter) 
        logger.addHandler(console_handler)
    
    # --- Rotating File Handler ---
    if not any(h.get_name() == "app_file_handler" for h in logger.handlers):
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
        )
        file_handler.set_name("app_file_handler")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(log_format)
        file_handler.addFilter(memory_filter) 
        logger.addHandler(file_handler)

    logging.info("--- Logging initialized ---")
    logging.info(f"Log level set to: {log_level_str}")
    logging.info(f"Log files at: {log_file}")

    # --- ADDED: Error Analytics Handler ---
    if analytics_service and not any(isinstance(h, AnalyticsLogHandler) for h in logger.handlers):
        analytics_config = config_loader.get_config("error_analytics_config.json")
        if analytics_config.get("enabled", False): 
            analytics_handler = AnalyticsLogHandler(analytics_service, level=logging.ERROR)
            logger.addHandler(analytics_handler)
            logging.info("Error analytics handler initialized.")
    # --- END ADDED SECTION ---

    