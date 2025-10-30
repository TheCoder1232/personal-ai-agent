from unittest.mock import MagicMock, AsyncMock
import pytest
import pytest_asyncio
import asyncio
from core.event_dispatcher import EventDispatcher

# ... (rest of the imports)

@pytest_asyncio.fixture
async def dispatcher(mock_service_locator):
    """Returns a new EventDispatcher instance for each test."""
    # Configure the mock config loader for EventDispatcher
    mock_service_locator.mock_config_loader.get_config.return_value = {
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
    # Start the dispatcher loop in the background for tests
    dispatcher_instance = EventDispatcher(mock_service_locator.mock_config_loader)
    await dispatcher_instance.start()
    yield dispatcher_instance
    # Stop the dispatcher loop after tests
    await dispatcher_instance.stop()

@pytest.mark.asyncio
async def test_subscribe_adds_handler(dispatcher):
    """Tests that a handler is correctly subscribed to an event."""
    handler = MagicMock()
    dispatcher.subscribe("TEST_EVENT", handler)
    
    assert "TEST_EVENT" in dispatcher._listeners
    assert handler in dispatcher._listeners["TEST_EVENT"]

@pytest.mark.asyncio
async def test_unsubscribe_removes_handler(dispatcher):
    """Tests that a handler is correctly unsubscribed."""
    handler = MagicMock()
    dispatcher.subscribe("TEST_EVENT", handler)
    dispatcher.unsubscribe("TEST_EVENT", handler)
    
    assert not dispatcher._listeners.get("TEST_EVENT")

@pytest.mark.asyncio
async def test_publish_calls_async_handler(dispatcher):
    """Tests that publish correctly calls an async handler."""
    handler = AsyncMock()
    dispatcher.subscribe("ASYNC_EVENT", handler)
    
    await dispatcher.publish("ASYNC_EVENT", data="test")
    await asyncio.sleep(0.1) # Give the dispatcher a moment to process
    
    handler.assert_awaited_once_with(data="test")

@pytest.mark.asyncio
async def test_publish_calls_sync_handler(dispatcher):
    """Tests that publish correctly calls a synchronous handler."""
    handler = MagicMock()
    dispatcher.subscribe("SYNC_EVENT", handler)
    
    await dispatcher.publish("SYNC_EVENT", data="sync_test")
    await asyncio.sleep(0.1) # Give the dispatcher a moment to process
    
    handler.assert_called_once_with(data="sync_test")

@pytest.mark.asyncio
async def test_publish_handles_handler_exceptions(dispatcher):
    """Tests that the dispatcher continues even if a handler fails."""
    good_handler = AsyncMock()
    bad_handler = AsyncMock(side_effect=Exception("Test Failure"))
    
    dispatcher.subscribe("EXCEPTION_EVENT", good_handler)
    dispatcher.subscribe("EXCEPTION_EVENT", bad_handler)
    
    # Should not raise an exception
    await dispatcher.publish("EXCEPTION_EVENT")
    await asyncio.sleep(0.1) # Give the dispatcher a moment to process
    
    good_handler.assert_awaited_once()
    bad_handler.assert_awaited_once()

@pytest.mark.asyncio
async def test_publish_sync_handles_handler_exceptions(dispatcher):
    """Tests that the dispatcher continues if a synchronous handler fails."""
    good_handler = MagicMock()
    bad_handler = MagicMock(side_effect=Exception("Test Failure"))
    
    dispatcher.subscribe("SYNC_EXCEPTION_EVENT", good_handler)
    dispatcher.subscribe("SYNC_EXCEPTION_EVENT", bad_handler)
    
    # Should not raise an exception
    await dispatcher.publish("SYNC_EXCEPTION_EVENT") # Use async publish
    await asyncio.sleep(0.1) # Give the dispatcher a moment to process
    
    good_handler.assert_called_once()
    bad_handler.assert_called_once()
