# file: utils/config_loader.py

import json
import os
import logging
import datetime  # --- ADDED ---
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
        # No hardcoded defaults; configs are loaded dynamically from disk

    def load_all_configs(self):
        """Loads all existing .json config files from the config directory."""
        # Clear current cache
        self.configs = {}
        # Load any JSON files present
        for path in sorted(self.config_dir.glob("*.json")):
            loaded = self._load_config(path.name)
            self.configs[path.name] = loaded

    def _load_config(self, filename: str) -> Dict:
        """Loads a single config file. If missing or invalid, returns an empty dict."""
        file_path = self.config_dir / filename
        
        if not file_path.exists():
            self.logger.warning(f"Config not found: {filename}. Using empty settings.")
            return {}
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            self.logger.error(f"Error reading {filename}. Backing up and using empty settings.") # --- Use logger
            
            # --- MODIFIED: Replaced 'pd' with 'datetime' ---
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            backup_path = file_path.with_suffix(f"{file_path.suffix}.{timestamp}.bak")
            # --- END MODIFIED SECTION ---
            
            try:
                file_path.rename(backup_path)
                self.logger.info(f"Backed up corrupted config to: {backup_path}")
            except (IOError, OSError) as e_rename:
                self.logger.error(f"Failed to rename corrupted config {filename}: {e_rename}")

            return {} # Use empty settings as recovery
        except (IOError, OSError) as e:
            self.logger.error(f"Failed to load {filename}: {e}") # --- Use logger
            return {} # Use empty settings as recovery
        except Exception as e:
            self.logger.error(f"Unexpected error loading {filename}: {e}") # --- Use logger
            return {}

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
        except (IOError, OSError) as e:
            self.logger.error(f"Failed to save {filename}: {e}") # --- Use logger
            # Raise our custom exception
            raise ConfigurationError(f"Could not write to file {filename}: {e}") from e
        except Exception as e:
            self.logger.error(f"Unexpected error saving {filename}: {e}") # --- Use logger
            raise ConfigurationError(f"Unexpected error saving {filename}: {e}") from e

    def get_data_dir(self) -> Path:
        """
        Returns the root directory for all app data (configs, logs, etc.).
        This implements the method expected by the Protocol in logger.py.
        """
        return self.config_dir

    def get(self, config_name: str, key: str, default: Any = None) -> Any:
        """Convenience method to get a specific key from a config file."""
        return self.get_config(config_name).get(key, default)