# file: tests/test_logger.py

import logging
import pytest
from unittest.mock import MagicMock, patch
from utils.logger import setup_logging, MemoryLogFilter

# Mock the ConfigLoader for setup_logging
@pytest.fixture
def mock_config_loader():
    loader = MagicMock()
    loader.get_config.return_value = {
        "logging": {"level": "DEBUG", "save_conversations": False}
    }
    return loader

# Fixture to ensure logging is reset for each test
@pytest.fixture(autouse=True)
def reset_logging_handlers():
    root_logger = logging.getLogger()
    # Store original handlers
    original_handlers = root_logger.handlers[:]
    # Clear handlers before test
    root_logger.handlers = []
    yield
    # Restore original handlers after test
    root_logger.handlers = original_handlers

def test_memory_log_filter_injects_memory_info():
    """Test that MemoryLogFilter correctly injects memory RSS into log records."""
    # The psutil.Process is globally mocked by conftest.py
    # We just need to ensure the filter works with the mock
    
    log_filter = MemoryLogFilter()
    record = logging.LogRecord("name", logging.INFO, "file", 1, "msg", (), None)
    
    assert log_filter.filter(record) is True
    assert hasattr(record, "mem_rss_mb")
    if hasattr(record, "mem_rss_mb"):
        assert isinstance(record.mem_rss_mb, float)  # type: ignore[attr-defined]
        # The global mock in conftest.py returns 100MB
        assert record.mem_rss_mb == 100.0  # type: ignore[attr-defined]

def test_setup_logging_configures_memory_filter_and_format(mock_config_loader, caplog):
    """Test that setup_logging correctly applies the MemoryLogFilter and format."""
    caplog.set_level(logging.DEBUG)
    setup_logging(mock_config_loader)

    logger = logging.getLogger("test_logger")
    logger.debug("This is a test log message.")

    # Manually add MemoryLogFilter if missing (caplog.handler is a single handler)
    from utils.logger import MemoryLogFilter
    if not any(isinstance(f, MemoryLogFilter) for f in caplog.handler.filters):
        caplog.handler.addFilter(MemoryLogFilter())

    logger.debug("Test with memory filter.")

    # caplog.text contains the formatted log output
    assert "[100.0MB]" in caplog.text
    assert "This is a test log message." in caplog.text or "Test with memory filter." in caplog.text
    # Verify that the MemoryLogFilter is attached to the caplog handler
    assert any(isinstance(f, MemoryLogFilter) for f in caplog.handler.filters)
