# file: utils/logger.py

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(config_loader):
    """
    Configures the global logging system.
    
    - Logs to console
    - Logs to rotating files in the app's data directory
    """
    
    # Get log level from config, default to INFO
    log_config = config_loader.get_config("system_config.json").get("logging", {})
    log_level_str = log_config.get("level", "INFO")
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    
    # Define log directory
    # Using Path.home() / ".PersonalAIAgent" is a good cross-platform
    # alternative to %APPDATA%
    log_dir = Path.home() / ".PersonalAIAgent" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "agent.log"
    
    # Define log format
    log_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"
    )
    
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # --- Console Handler ---
    # Avoid adding duplicate handlers
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(log_format)
        logger.addHandler(console_handler)
    
    # --- Rotating File Handler ---
    # Log up to 5 files, 5MB each
    if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)

    logging.info("--- Logging initialized ---")
    logging.info(f"Log level set to: {log_level_str}")
    logging.info(f"Log files at: {log_file}")