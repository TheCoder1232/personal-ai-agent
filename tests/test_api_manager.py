# file: tests/test_api_manager.py

import pytest
from unittest.mock import patch, MagicMock, call
from litellm import exceptions as litellm_exceptions

from core.api_manager import ApiManager
from core.exceptions import *

@pytest.fixture
def api_manager(mock_service_locator):
    """Initializes ApiManager with a mocked locator."""
    # Configure mock config for active and fallback providers
    mock_service_locator.mock_config_loader.get_config.return_value = {
        "active_provider": "test_provider",
        "active_model": "test_model",
        "fallback_provider": "fallback_provider",
        "fallback_model": "fallback_model",
        "providers": {
            "test_provider": {"api_key": "test_key"},
            "fallback_provider": {"api_key": "fallback_key"}
        }
    }
    return ApiManager(mock_service_locator)

@patch('litellm.completion')
def test_chat_stream_success(mock_litellm_completion, api_manager):
    """Tests a successful chat stream call."""
    # Mock the streaming response
    mock_chunk = MagicMock()
    mock_chunk.choices[0].delta.content = "Hello"
    mock_litellm_completion.return_value = iter([mock_chunk])
    
    response = list(api_manager.chat_stream([], "system prompt"))
    
    assert response == ["Hello"]
    mock_litellm_completion.assert_called_once()
    call_args = mock_litellm_completion.call_args[1]
    assert call_args['model'] == "test_provider/test_model"

@patch('core.api_manager.ApiManager._completion_with_retry')
def test_chat_stream_fallback_on_rate_limit(mock_completion_with_retry, api_manager):
    """Tests that the fallback provider is used on RateLimitError."""
    mock_chunk = MagicMock()
    mock_chunk.choices[0].delta.content = "Fallback response"
    mock_completion_with_retry.side_effect = [
        litellm_exceptions.RateLimitError(message="Rate limit exceeded", response=MagicMock(), llm_provider="test_provider", model="test_model"),
        iter([mock_chunk])
    ]
    response = list(api_manager.chat_stream([], "system prompt"))
    assert response == ["Fallback response"], f"Received {response}, expected ['Fallback response']"
    assert mock_completion_with_retry.call_count == 2
    fallback_call_args = mock_completion_with_retry.call_args_list[1].kwargs
    assert fallback_call_args['model'] == "fallback_provider/fallback_model"

@patch('litellm.completion')
def test_chat_stream_retry_on_connection_error(mock_litellm_completion, api_manager):
    """Tests the retry logic on connection errors."""
    # Mock the streaming response for the successful call
    mock_chunk = MagicMock()
    mock_chunk.choices[0].delta.content = "Success after retry"
    
    # Simulate ConnectionError, then success
    mock_litellm_completion.side_effect = [
        litellm_exceptions.APIConnectionError(message="Connection failed", request=MagicMock(), llm_provider="test_provider", model="test_model"),
        iter([mock_chunk])
    ]
    
    # Temporarily reduce the number of retry attempts for the test
    with patch('tenacity.stop_after_attempt', return_value=MagicMock(return_value=True)):
         list(api_manager.chat_stream([], "system prompt"))

    # The retry decorator is on _completion_with_retry, so litellm.completion is called multiple times
    assert mock_litellm_completion.call_count >= 2

@patch('litellm.completion')
def test_chat_stream_handles_authentication_error(mock_litellm_completion, api_manager):
    """Tests that a non-retriable authentication error is handled gracefully."""
    mock_litellm_completion.side_effect = litellm_exceptions.AuthenticationError(
        message="Invalid API key", response=MagicMock(), llm_provider="test_provider", model="test_model"
    )
    
    response = list(api_manager.chat_stream([], "system prompt"))
    
    assert "Error: API Key Error" in response[0]
    mock_litellm_completion.assert_called_once()
