# file: tests/conftest.py

import pytest
import asyncio
from unittest.mock import MagicMock, patch
from pathlib import Path

# --- Mocks for Core Components ---

@pytest.fixture(scope="function")
def mock_service_locator():
    """Mocks the ServiceLocator and its commonly used services."""
    locator = MagicMock()
    
    # Mock ConfigLoader
    mock_config_loader = MagicMock()
    mock_config_loader.get_config.return_value = {}
    mock_config_loader.get.return_value = None
    locator.resolve.return_value = mock_config_loader
    
    # Make it easy to access and configure mocks
    locator.mock_config_loader = mock_config_loader
    
    # Mock EventDispatcher
    mock_event_dispatcher = MagicMock()
    # Make publish_sync a synchronous mock
    mock_event_dispatcher.publish_sync = MagicMock() 
    # Make publish an async mock
    async def async_magic_mock(*args, **kwargs):
        pass
    mock_event_dispatcher.publish = MagicMock(side_effect=async_magic_mock)
    
    # Configure resolve to return the correct mock
    def resolve_side_effect(service_name):
        if service_name == "config_loader":
            return mock_config_loader
        if service_name == "event_dispatcher":
            return mock_event_dispatcher
        return MagicMock()
        
    locator.resolve.side_effect = resolve_side_effect
    locator.mock_event_dispatcher = mock_event_dispatcher
    
    return locator

@pytest.fixture
def temp_config_dir(tmp_path):
    """Creates a temporary directory for config files."""
    return tmp_path

# --- Pytest-Asyncio Configuration ---

@pytest.fixture(scope="session")
def event_loop():
    """Overrides the default event loop to enable session-scoped async fixtures."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

# --- Global Mock for psutil.Process ---
# This ensures that MemoryLogFilter (and other components using psutil) use a mock
# process during tests, preventing actual system calls.
class MockProcess:
    def memory_info(self):
        return MagicMock(rss=100 * 1024 * 1024) # Default 100MB RSS

mock_psutil_process = MockProcess()

@pytest.fixture(scope="session", autouse=True)
def mock_psutil_process_globally():
    """Globally patches psutil.Process for all tests."""
    with patch('psutil.Process', return_value=mock_psutil_process):
        yield
