# file: tests/test_memory_manager.py

import asyncio
import logging
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

# Make sure psutil is mocked before it's imported by the manager
# This is a common pattern for mocking modules that are imported at the top level
class MockProcess:
    def memory_info(self):
        return MagicMock(rss=100 * 1024 * 1024) # Default 100MB RSS

mock_psutil_process = MockProcess()

# The patch needs to target where the object is *looked up*, which is in the memory_manager module
psutil_patch = patch('core.memory_manager.psutil.Process', return_value=mock_psutil_process)
psutil_patch.start()

# Now we can import the class we are testing
from core.memory_manager import MemoryManager

# Stop the patch after the tests are done to avoid side effects
@pytest.fixture(scope="session", autouse=True)
def stop_psutil_patch():
    yield
    psutil_patch.stop()

@pytest.fixture
def mock_service_locator():
    """Fixture to create a mock ServiceLocator that returns consistent mocks."""
    locator = MagicMock()
    
    # Store mocks to be returned by resolve
    mocks = {
        "config_loader": MagicMock(),
        "event_dispatcher": AsyncMock()
    }
    
    # side_effect function to return the correct mock
    locator.resolve.side_effect = lambda service: mocks.get(service)
    
    # Attach mocks for easy access in tests
    locator.mocks = mocks
    
    return locator

@pytest.fixture
def memory_manager(mock_service_locator):
    """Fixture to create a MemoryManager instance with mocked dependencies."""
    # Configure the mock config_loader *before* MemoryManager is instantiated
    config_loader = mock_service_locator.mocks["config_loader"]
    config_loader.get_config.return_value = {
        "enabled": True,
        "threshold_mb": 150,
        "monitor_interval_sec": 1,
        "log_level": "DEBUG"
    }
    
    # Now, when MemoryManager is created, its __init__ will call _load_config
    # and use the mock we just configured.
    manager = MemoryManager(mock_service_locator)
    
    return manager

# --- Test Cases ---

def test_initialization_and_config_loading(memory_manager):
    """Test that the manager initializes correctly and loads its config."""
    assert memory_manager.enabled is True
    assert memory_manager.threshold_mb == 150
    assert memory_manager.interval_sec == 1
    assert memory_manager.logger.level == logging.DEBUG
    
    config_loader = memory_manager.locator.resolve("config_loader")
    config_loader.get_config.assert_called_once_with("memory_config.json")

def test_monitoring_disabled_by_config(mock_service_locator):
    """Test that monitoring does not start if disabled in config."""
    config_loader = mock_service_locator.resolve("config_loader")
    config_loader.get_config.return_value = {"enabled": False}
    
    manager = MemoryManager(mock_service_locator)
    manager._load_config()
    
    manager.start_monitoring()
    
    assert manager._monitor_task is None

def test_track_component(memory_manager):
    """Test that components can be tracked."""
    memory_manager.track_component("test_plugin")
    assert "test_plugin" in memory_manager.tracked_components
    
    # Test tracking the same component again (should log a warning but not fail)
    memory_manager.track_component("test_plugin")
    assert "test_plugin" in memory_manager.tracked_components

def test_get_current_usage_mb(memory_manager):
    """Test fetching current memory usage."""
    with patch.object(memory_manager.process, 'memory_info', return_value=MagicMock(rss=200 * 1024 * 1024)):
        usage = memory_manager.get_current_usage_mb()
        assert usage == 200.0

@pytest.mark.asyncio
async def test_monitoring_task_stops_correctly(memory_manager):
    """Test that the monitoring task can be started and stopped."""
    memory_manager.start_monitoring()
    assert memory_manager._monitor_task is not None
    assert not memory_manager._monitor_task.done()
    
    await memory_manager.stop_monitoring()
    
    assert memory_manager._monitor_task is None

@pytest.mark.asyncio
async def test_monitor_loop_publishes_event_on_high_usage(memory_manager):
    """Test that a HIGH_USAGE event is published when memory exceeds the threshold."""
    with patch.object(memory_manager.process, 'memory_info', return_value=MagicMock(rss=200 * 1024 * 1024)):
        original_sleep = asyncio.sleep
        async def mock_sleep_and_cancel(delay):
            await original_sleep(0.01)
            memory_manager._monitor_task.cancel()
        with patch('asyncio.sleep', mock_sleep_and_cancel):
            await memory_manager.monitor_resource_usage()
    event_dispatcher = memory_manager.locator.resolve("event_dispatcher")
    event_dispatcher.publish.assert_called_once_with(
        "MEMORY_EVENT.HIGH_USAGE",
        current_mb=200.0,
        threshold_mb=150
    )

@pytest.mark.asyncio
async def test_monitor_loop_does_not_publish_event_on_normal_usage(memory_manager):
    """Test that no event is published when memory is below the threshold."""
    with patch.object(memory_manager.process, 'memory_info', return_value=MagicMock(rss=120 * 1024 * 1024)):
        original_sleep = asyncio.sleep
        async def mock_sleep_and_cancel(delay):
            await original_sleep(0.01)
            memory_manager._monitor_task.cancel()
        with patch('asyncio.sleep', mock_sleep_and_cancel):
            await memory_manager.monitor_resource_usage()
    event_dispatcher = memory_manager.locator.resolve("event_dispatcher")
    event_dispatcher.publish.assert_not_called()
