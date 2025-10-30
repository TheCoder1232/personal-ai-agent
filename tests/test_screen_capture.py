# file: tests/test_screen_capture.py

import pytest
from unittest.mock import patch, MagicMock, AsyncMock, call
import asyncio

# Mock the entire mss library before importing the plugin
with patch.dict('sys.modules', {'mss': MagicMock(), 'mss.tools': MagicMock()}):
    from plugins.screen_capture import ScreenCapturePlugin

@pytest.fixture
def screen_capture_plugin(mock_service_locator):
    """Initializes the ScreenCapturePlugin with a mocked locator."""
    # Mock the config loader to return that the plugin is enabled
    mock_service_locator.mock_config_loader.get_config.return_value = {
        "plugins": {"ScreenCapture": {"enabled": True}}
    }
    return ScreenCapturePlugin(mock_service_locator)

@pytest.mark.asyncio
@patch('asyncio.to_thread')
async def test_on_capture_request_success(mock_to_thread, screen_capture_plugin):
    """Tests the successful execution of the on_capture_request event handler."""
    # Arrange
    # Configure mock_to_thread to return values for capture_screen and process_image
    mock_to_thread.side_effect = [
        (b'raw_bytes', (1920, 1080)), # Return for capture_screen
        "base64_encoded_string"       # Return for process_image
    ]
    
    # Act
    await screen_capture_plugin.on_capture_request()
    
    # Assert
    # Verify that asyncio.to_thread was called for both capture_screen and process_image
    assert mock_to_thread.call_count == 2
    mock_to_thread.assert_has_calls([
        call(screen_capture_plugin.capture_screen), # First call
        call(screen_capture_plugin.process_image, b'raw_bytes', (1920, 1080)) # Second call
    ])
    
    # Verify that the correct events were published
    mock_dispatcher = screen_capture_plugin.locator.resolve("event_dispatcher")
    
    # Check for PLUGIN_EVENT.SCREEN_CAPTURED event
    mock_dispatcher.publish.assert_any_call(
        'PLUGIN_EVENT.SCREEN_CAPTURED', 
        image_data="base64_encoded_string", 
        format="base64"
    )
    # Check for NOTIFICATION_EVENT.INFO and UI_EVENT.OPEN_CHAT events
    mock_dispatcher.publish.assert_any_call(
        'NOTIFICATION_EVENT.INFO',
        title="Screen Captured",
        message="Screenshot attached. Opening chat..."
    )
    mock_dispatcher.publish.assert_any_call('UI_EVENT.OPEN_CHAT')

@pytest.mark.asyncio
@patch('asyncio.to_thread')
async def test_on_capture_request_failure(mock_to_thread, screen_capture_plugin):
    """Tests the failure case for the on_capture_request handler."""
    # Arrange
    mock_to_thread.side_effect = Exception("Capture failed")
    
    # Act
    await screen_capture_plugin.on_capture_request()
    
    # Assert
    mock_dispatcher = screen_capture_plugin.locator.resolve("event_dispatcher")
    mock_dispatcher.publish.assert_any_call(
        "NOTIFICATION_EVENT.ERROR",
        title="Capture Failed",
        message="Capture failed"
    )
