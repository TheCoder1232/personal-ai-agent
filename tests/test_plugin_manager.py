# file: tests/test_plugin_manager.py

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path

# Import the classes to be tested
from core.plugin_manager import PluginManager
from core.exceptions import PluginLoadError
from plugins import PluginBase

# --- Mocks and Fixtures ---

# A mock base plugin for testing discovery and loading
class MockPlugin(PluginBase):
    def get_metadata(self):
        return {"name": "mock_plugin", "version": "1.0"}
    def initialize(self):
        pass # Success

# A mock plugin that fails during its own initialization
class FailingPlugin(PluginBase):
    def get_metadata(self):
        return {"name": "failing_plugin", "version": "1.0"}
    def initialize(self):
        raise ValueError("Initialization failed")

@pytest.fixture
def mock_service_locator():
    """Fixture for a mock ServiceLocator."""
    locator = MagicMock()
    
    # Provide mocks for all services the PluginManager depends on
    mock_config_loader = MagicMock()
    mock_config_loader.get.return_value = True # lazy_load_enabled = True
    
    locator.resolve.side_effect = lambda service: {
        "event_dispatcher": AsyncMock(),
        "memory_manager": MagicMock(),
        "config_loader": mock_config_loader
    }.get(service)
    
    return locator

@pytest.fixture
def plugin_manager(mock_service_locator, tmp_path):
    """Fixture for a PluginManager instance that uses a temporary plugins directory."""
    # Create a dummy plugins directory
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    
    # Create a dummy plugin file
    plugin_file = plugins_dir / "mock_plugin_file.py"
    plugin_file.write_text(
        "from plugins import PluginBase\n"
        "class MockPlugin(PluginBase):\n"
        "    def get_metadata(self):\n"
        "        return {'name': 'mock_plugin'}\n"
        "    def initialize(self):\n"
        "        pass\n"
        "class FailingPlugin(PluginBase):\n"
        "    def get_metadata(self):\n"
        "        return {'name': 'failing_plugin'}\n"
        "    def initialize(self):\n"
        "        raise ValueError('Init failed')\n"
    )
    
    # Instantiate the manager first
    manager = PluginManager(mock_service_locator)
    
    # Now, override its plugins_dir and re-run discovery
    manager.plugins_dir = plugins_dir
    manager._plugin_registry.clear() # Clear any results from initial discovery
    manager._discover_plugins_sync() # Re-discover from the temp directory
    
    yield manager

# --- Test Cases ---

def test_plugin_discovery(plugin_manager):
    """Test that plugins are discovered correctly on initialization."""
    # The _discover_plugins_sync method is called in __init__
    assert "mock_plugin" in plugin_manager._plugin_registry
    assert "failing_plugin" in plugin_manager._plugin_registry
    assert len(plugin_manager._plugin_registry) == 2
    
    # Check that no plugins are loaded yet
    assert len(plugin_manager._loaded_plugins) == 0

@pytest.mark.asyncio
async def test_lazy_loading_get_plugin(plugin_manager):
    """Test that get_plugin loads a plugin on demand with lazy loading."""
    event_dispatcher = plugin_manager.locator.resolve("event_dispatcher")
    event_dispatcher.publish.reset_mock()
    plugin = await plugin_manager.get_plugin("mock_plugin")
    assert plugin is not None
    assert "mock_plugin" in plugin_manager._loaded_plugins
    # Ensure the AsyncMock was awaited with correct arguments
    event_dispatcher.publish.assert_awaited_with(
        "PLUGIN_EVENT.LOADED",
        plugin_id="mock_plugin",
        metadata={'name': 'mock_plugin'}
    )

@pytest.mark.asyncio
async def test_get_nonexistent_plugin_raises_error(plugin_manager):
    """Test that getting a plugin that was not discovered raises an error."""
    with pytest.raises(PluginLoadError, match="Plugin 'nonexistent' is not discovered."):
        await plugin_manager.get_plugin("nonexistent")

@pytest.mark.asyncio
async def test_eager_loading_loads_all_plugins(mock_service_locator, tmp_path):
    """Test that all discovered plugins are loaded when lazy loading is disabled."""
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    plugin_file = plugins_dir / "mock_plugin_file.py"
    plugin_file.write_text(
        "from plugins import PluginBase\n"
        "class MockPlugin(PluginBase):\n"
        "    def get_metadata(self): return {'name': 'mock_plugin'}\n"
        "    def initialize(self): pass\n"
    )
    mock_service_locator.resolve("config_loader").get.return_value = False
    manager = PluginManager(mock_service_locator)
    manager.plugins_dir = plugins_dir   # Patch after instance is created
    manager._plugin_registry.clear()
    manager._discover_plugins_sync()
    await manager.discover_and_load_plugins()
    assert "mock_plugin" in manager._loaded_plugins
    assert len(manager._loaded_plugins) == 1

@pytest.mark.asyncio
async def test_loading_failing_plugin_raises_error(plugin_manager):
    """Test that if a plugin fails to initialize, it raises PluginLoadError."""
    event_dispatcher = plugin_manager.locator.resolve("event_dispatcher")
    event_dispatcher.publish.reset_mock()
    with pytest.raises(PluginLoadError, match="Plugin 'failing_plugin' failed during initialize()"):
        await plugin_manager.get_plugin("failing_plugin")
    assert "failing_plugin" not in plugin_manager._loaded_plugins
    # Ensure the AsyncMock was awaited with correct arguments
    event_dispatcher.publish.assert_awaited_with(
        "ERROR_EVENT.PLUGIN_CRASH",
        plugin_name="failing_plugin",
        error="Init failed"
    )

@pytest.mark.asyncio
async def test_plugin_loading_tracks_with_memory_manager(plugin_manager):
    """
    Test the integration with MemoryManager: successful load should track the component.
    """
    memory_manager = plugin_manager.locator.resolve("memory_manager")
    memory_manager.track_component.reset_mock()
    await plugin_manager.get_plugin("mock_plugin")
    memory_manager.track_component.assert_called_once_with("plugin:mock_plugin")

@pytest.mark.asyncio
async def test_failing_plugin_does_not_track_with_memory_manager(plugin_manager):
    """
    Test that if a plugin fails to load, it is NOT tracked by the MemoryManager.
    """
    memory_manager = plugin_manager.locator.resolve("memory_manager")
    
    # Attempt to load the failing plugin
    with pytest.raises(PluginLoadError):
        await plugin_manager.get_plugin("failing_plugin")
        
    # Assert that track_component was NOT called
    memory_manager.track_component.assert_not_called()
