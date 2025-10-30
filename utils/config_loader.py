# file: utils/config_loader.py

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any
from core.exceptions import ConfigurationError

class ConfigLoader:
    """
    Manages loading and saving multiple JSON configuration files.
    
    Creates default config files if they don't exist.
    """
    
    def __init__(self, config_dir: Path):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.configs: Dict[str, Any] = {}
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Define default structures as per your plan
        self.defaults = {
            "ui_config.json": {
                "theme": "system",
                "popup": {"x": 100, "y": 100, "width": 400, "height": 600},
                "minimize_to_tray": True,
                "markdown_rendering": True
            },
            "models_config.json": {
                "active_provider": "gemini",
                "active_model": "gemini-1.5-flash",
                "providers": {
                    "gemini": {"api_key": "", "models": ["gemini-1.5-flash", "gemini-1.5-pro"]},
                    "ollama": {"base_url": "http://localhost:11434", "models": []},
                    "openrouter": {"api_key": "", "models": []}
                }
            },
            "mcp_config.json": {
                "servers": [
                    {
                        "id": "filesystem",
                        "name": "File System",
                        "command": "python",
                        "args": ["-m", "mcp_server_filesystem"],
                        "enabled": True
                    }
                ]
            },
            # --- NEW: Command Config ---
            "commands_config.json": {
                "max_history": 50
            },
            # --- NEW: Context Config ---
            "context_config.json": {
                "max_messages": 50,
                "pruning_strategy": "fifo",
                "summarize_threshold": 20
            },
            # --- ADDED: Memory Config ---
            "memory_config.json": {
                "monitor_interval_sec": 60,
                "threshold_mb": 500,
                "log_level": "INFO",
                "enabled": True
            },
            # --- END ADDED SECTION ---
            "system_config.json": {
                "hotkeys": {
                    "open_chat": "<ctrl>+<shift>+<space>",
                    "screen_capture": "<ctrl>+<shift>+x"
                },
                "logging": {"level": "INFO", "save_conversations": False},
                
                # --- REMOVED 'context' block ---
                
                "event_priorities": {
                    "DEFAULT": 50,
                    "ERROR_EVENT": 0,
                    "SYSTEM_EVENT": 5,
                    "UI_EVENT": 10,
                    "USER_ACTION": 10,
                    "MODEL_RESPONSE": 20,
                    "LOGGING_EVENT": 100
                }
            }
        }

    def load_all_configs(self):
        """Loads all defined config files into memory."""
        for filename, default_data in self.defaults.items():
            self.configs[filename] = self._load_config(filename, default_data)

    def _load_config(self, filename: str, default_data: Dict) -> Dict:
        """Loads a single config file, creating it if it doesn't exist."""
        file_path = self.config_dir / filename
        
        if not file_path.exists():
            self.logger.warning(f"Creating default config: {filename}") # --- Use logger
            try:
                self.save_config(filename, default_data)
            except ConfigurationError as e: # --- Handle save error
                self.logger.error(f"Failed to create default config {filename}: {e}")
                return default_data # Return default even if save failed
            return default_data
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            self.logger.error(f"Error reading {filename}. Backing up and creating new default.") # --- Use logger
            file_path.rename(file_path.with_suffix(f"{file_path.suffix}.bak"))
            try:
                self.save_config(filename, default_data)
            except ConfigurationError as e_save:
                self.logger.error(f"Failed to create new default {filename} after parse error: {e_save}")
            return default_data # Return default as recovery
        except (IOError, OSError) as e:
            self.logger.error(f"Failed to load {filename}: {e}") # --- Use logger
            return default_data # Return default as recovery
        except Exception as e:
            self.logger.error(f"Unexpected error loading {filename}: {e}") # --- Use logger
            return default_data

    def get_config(self, filename: str) -> Dict:
        """Gets a specific loaded config."""
        return self.configs.get(filename, {})

    def save_config(self, filename: str, data: Dict):
        """Saves data to a specific config file."""
        file_path = self.config_dir / filename
        self.configs[filename] = data # Update in-memory cache
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        # --- START: MODIFIED SECTION ---
        except (IOError, OSError) as e:
            self.logger.error(f"Failed to save {filename}: {e}") # --- Use logger
            # Raise our custom exception
            raise ConfigurationError(f"Could not write to file {filename}: {e}") from e
        except Exception as e:
            self.logger.error(f"Unexpected error saving {filename}: {e}") # --- Use logger
            raise ConfigurationError(f"Unexpected error saving {filename}: {e}") from e
        # --- END: MODIFIED SECTION ---

    def get(self, config_name: str, key: str, default: Any = None) -> Any:
        """Convenience method to get a specific key from a config file."""
        return self.get_config(config_name).get(key, default)