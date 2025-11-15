# file: utils/config_loader.py

import json
import os
import logging
import datetime
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
        self._defaults = {
            "ui_config.json": {"theme": "system"},
            "system_config.json": {
                "hotkeys": {
                    "open_chat": "<ctrl>+<shift>+<space>",
                    "screen_capture": "<ctrl>+<shift>+x"
                },
                "event_priorities": {
                    "DEFAULT": 50,
                    "ERROR_EVENT": 0,
                    "SYSTEM_EVENT": 5,
                    "UI_EVENT": 10,
                    "USER_ACTION": 10,
                    "MODEL_RESPONSE": 20,
                    "LOGGING_EVENT": 100
                }
            },
            "models_config.json": {
                "active_provider": "gemini",
                "active_model": "gemini-1.5-flash-latest",
                "providers": {
                    "gemini": {"api_key": "", "models": ["gemini-1.5-flash-latest"]},
                    "openrouter": {"api_key": "", "models": []},
                    "ollama": {"base_url": "http://localhost:11434", "models": []}
                }
            },
            "memory_config.json": {
                "enabled": True,
                "monitor_interval_sec": 60,
                "threshold_mb": 500,
                "log_level": "INFO"
            },
            "commands_config.json": {"max_history": 50},
            "context_config.json": {
                "max_messages": 50,
                "pruning_strategy": "fifo",
                "summarize_threshold": 20
            }
        }

    @property
    def defaults(self):
        """Public property to access the defaults dictionary, for tests."""
        return self._defaults

    def load_all_configs(self):
        """Loads all default and existing .json config files."""
        self.configs = {}
        
        # Ensure all default configs are loaded/created
        for filename, default_data in self._defaults.items():
            self.configs[filename] = self._load_config(filename, default_data)

        # Load any other JSON files present that are not in defaults
        for path in sorted(self.config_dir.glob("*.json")):
            if path.name not in self.configs:
                self.configs[path.name] = self._load_config(path.name, {})

    def _load_config(self, filename: str, default_data: Dict) -> Dict:
        """
        Loads a single config file. If missing, creates it with default_data.
        If invalid, backs it up and returns default_data.
        """
        file_path = self.config_dir / filename
        
        if not file_path.exists():
            self.logger.info(f"Config '{filename}' not found. Creating with defaults.")
            try:
                self.save_config(filename, default_data)
            except ConfigurationError as e:
                self.logger.error(f"Failed to create default config for {filename}: {e}")
                return {} # Return empty if creation fails
            return default_data
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            self.logger.error(f"Error reading {filename}. Backing up and using defaults.")
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            backup_path = file_path.with_suffix(f"{file_path.suffix}.{timestamp}.bak")
            try:
                file_path.rename(backup_path)
                self.logger.info(f"Backed up corrupted config to: {backup_path}")
            except (IOError, OSError) as e_rename:
                self.logger.error(f"Failed to rename corrupted config {filename}: {e_rename}")
            return default_data
        except (IOError, OSError) as e:
            self.logger.error(f"Failed to load {filename}: {e}")
            return default_data
        except Exception as e:
            self.logger.error(f"Unexpected error loading {filename}: {e}")
            return default_data

    def get_config(self, filename: str) -> Dict:
        """Gets a specific loaded config."""
        if filename not in self.configs:
            # If a config is requested that wasn't in defaults and didn't exist at startup
            self.logger.warning(f"Config '{filename}' was not loaded at startup. Returning empty.")
        return self.configs.get(filename, {})

    def save_config(self, filename: str, data: Dict):
        """Saves data to a specific config file."""
        file_path = self.config_dir / filename
        self.configs[filename] = data
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except (IOError, OSError) as e:
            self.logger.error(f"Failed to save {filename}: {e}")
            raise ConfigurationError(f"Could not write to file {filename}: {e}") from e
        except Exception as e:
            self.logger.error(f"Unexpected error saving {filename}: {e}")
            raise ConfigurationError(f"Unexpected error saving {filename}: {e}") from e

    def get_data_dir(self) -> Path:
        """Returns the root directory for all app data."""
        return self.config_dir

    def get(self, config_name: str, key: str, default: Any = None) -> Any:
        """Convenience method to get a specific key from a config file."""
        return self.get_config(config_name).get(key, default)