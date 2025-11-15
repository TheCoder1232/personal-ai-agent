# file: tests/test_logger.py

import logging
import pytest
from unittest.mock import MagicMock, patch
from utils.logger import setup_logging, MemoryLogFilter
from pathlib import Path

# Mock the ConfigLoader for setup_logging
@pytest.fixture
def mock_config_loader(tmp_path: Path):
    loader = MagicMock()
    loader.get_config.return_value = {
        "logging": {"level": "DEBUG", "save_conversations": False}
    }
    # Configure get_data_dir to return the temporary test directory
    loader.get_data_dir.return_value = tmp_path
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

    root_logger = logging.getLogger()
    
    app_handlers = [
        h for h in root_logger.handlers 
        if h.get_name() in ["app_console_handler", "app_file_handler"]
    ]
    
    assert len(app_handlers) == 2, f"Expected 2 app handlers, found {len(app_handlers)}"
    
    # Check that both app handlers have the filter
    for handler in app_handlers:
        assert any(isinstance(f, MemoryLogFilter) for f in handler.filters)

    # *** FIX: Apply the application's formatter to the caplog handler ***
    # This ensures the captured output is formatted correctly for the assertion.
    if app_handlers:
        app_formatter = app_handlers[0].formatter
        caplog.handler.setFormatter(app_formatter)
        # The filter must also be added to the caplog handler for the formatter to work
        if not any(isinstance(f, MemoryLogFilter) for f in caplog.handler.filters):
            caplog.handler.addFilter(MemoryLogFilter())

    # Log a message and check the output format from caplog
    logger = logging.getLogger("test_logger")
    logger.debug("This is a test log message.")
    
    assert "[100.0MB]" in caplog.text
    assert "This is a test log message." in caplog.text
