# file: tests/test_config_loader.py

import pytest
import json
from pathlib import Path
from unittest.mock import patch, mock_open

from utils.config_loader import ConfigLoader
from core.exceptions import ConfigurationError

@pytest.fixture
def config_loader(temp_config_dir):
    """Initializes ConfigLoader with a temporary directory."""
    return ConfigLoader(temp_config_dir)

def test_config_loader_creates_directory(temp_config_dir):
    """Tests if the config directory is created on initialization."""
    assert temp_config_dir.exists()
    assert temp_config_dir.is_dir()

def test_load_all_configs_creates_defaults(config_loader, temp_config_dir):
    """Tests that default config files are created if they don't exist."""
    config_loader.load_all_configs()
    
    for filename in config_loader.defaults.keys():
        assert (temp_config_dir / filename).exists()

def test_get_config_returns_loaded_data(config_loader):
    """Tests getting a loaded configuration."""
    config_loader.load_all_configs()
    ui_config = config_loader.get_config("ui_config.json")
    
    assert ui_config is not None
    assert ui_config["theme"] == "system"

def test_save_config_writes_to_file(config_loader, temp_config_dir):
    """Tests saving a configuration to a file."""
    test_data = {"key": "value"}
    filename = "test_config.json"
    
    # Manually add to defaults for this test
    config_loader.defaults[filename] = {}
    
    config_loader.save_config(filename, test_data)
    
    file_path = temp_config_dir / filename
    assert file_path.exists()
    with open(file_path, 'r') as f:
        assert json.load(f) == test_data

def test_load_config_handles_json_decode_error(config_loader, temp_config_dir):
    """Tests that a corrupt JSON file is handled gracefully."""
    filename = "corrupt_config.json"
    file_path = temp_config_dir / filename
    
    with open(file_path, 'w') as f:
        f.write("{'invalid_json':}")
        
    # Manually add to defaults
    default_data = {"default": True}
    config_loader.defaults[filename] = default_data
    
    # Load the corrupt file
    loaded_config = config_loader._load_config(filename, default_data)
    
    # Should return default data
    assert loaded_config == default_data
    # Should have created a backup
    assert (temp_config_dir / f"{filename}.bak").exists()

def test_save_config_raises_configuration_error_on_io_error(config_loader):
    """Tests that save_config raises ConfigurationError on file write failure."""
    with patch("builtins.open", mock_open()) as mocked_file:
        mocked_file.side_effect = IOError("Disk full")
        
        with pytest.raises(ConfigurationError):
            config_loader.save_config("any_file.json", {"data": "any"})

def test_load_all_configs_includes_memory_config_defaults(config_loader, temp_config_dir):
    """Tests that load_all_configs correctly includes memory_config.json defaults."""
    config_loader.load_all_configs()

    # Assert that the default memory config was created and loaded
    memory_config = config_loader.get_config("memory_config.json")
    assert memory_config["monitor_interval_sec"] == 60
    assert memory_config["threshold_mb"] == 500
    assert memory_config["log_level"] == "INFO"
    assert memory_config["enabled"] is True

    # Assert that the default commands config was created and loaded
    commands_config = config_loader.get_config("commands_config.json")
    assert commands_config["max_history"] == 50

    # Assert that the default context config was created and loaded
    context_config = config_loader.get_config("context_config.json")
    assert context_config["max_messages"] == 50
    assert context_config["pruning_strategy"] == "fifo"
    assert context_config["summarize_threshold"] == 20

    # Verify that the files exist on disk
    assert (temp_config_dir / "memory_config.json").exists()
    assert (temp_config_dir / "commands_config.json").exists()
    assert (temp_config_dir / "context_config.json").exists()
