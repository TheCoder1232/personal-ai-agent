# file: core/api_manager.py

import os
import logging
import asyncio
import litellm
from litellm import exceptions
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from typing import List, Dict, Generator, Optional, Iterator, Any
from core.service_locator import locator
from core.event_dispatcher import EventDispatcher
from utils.config_loader import ConfigLoader
# --- ADDED: Custom Exception Imports ---
from core.exceptions import (
    APIError,
    APIConnectionError,
    APIRateLimitError,
    APIAuthenticationError,
    APINotFoundError,
    APIConfigurationError
)

# This sets logging for LiteLLM to see its outputs
os.environ['LITELLM_LOG'] = 'DEBUG'

class ApiManager:
    """
    Manages all LLM API calls using LiteLLM.
    This single class replaces the BaseAPI, GeminiAPI, OllamaAPI,
    and OpenRouterAPI classes.
    """
    def __init__(self, locator):
        self.locator = locator
        self.events: EventDispatcher = self.locator.resolve("event_dispatcher")
        self.config: ConfigLoader = self.locator.resolve("config_loader")
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.events.subscribe("API_EVENT.TEST_CONNECTION", self.on_test_connection)
        self.events.subscribe("UI_EVENT.SETTINGS_CHANGED", self.load_provider_config)
        
        self.load_provider_config()

    def load_provider_config(self, *args, **kwargs):
        """
        Notifies the ApiManager that config *may* have changed.
        """
        self.logger.debug("API Manager config (re)loaded/notified.")
        # Removed global litellm.api_base_for setting, as it's
        # now passed as 'api_base' in the completion call, which is safer.

    # --- NEW: Decorator for retry logic ---
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(4),
        reraise=True,
        retry=retry_if_exception_type(APIConnectionError) | retry_if_exception_type(APIRateLimitError)
    )
    def _completion_with_retry(self, **kwargs) -> Any:
        """Internal synchronous call to litellm.completion with retries."""
        self.logger.debug(f"Attempting litellm.completion for model: {kwargs.get('model')}")
        try:
            return litellm.completion(**kwargs)
        
        # --- START: MODIFIED SECTION ---
        # Wrap litellm exceptions in our custom exceptions
        # Retriable errors
        except exceptions.APIConnectionError as e:
            self.logger.warning(f"LiteLLM API Connection Error (will retry): {e}")
            raise APIConnectionError(f"Connection error: {e}") from e
        except exceptions.RateLimitError as e:
            self.logger.warning(f"LiteLLM Rate Limit Error (will retry): {e}")
            raise APIRateLimitError(f"Rate limit exceeded: {e}") from e
        except exceptions.ServiceUnavailableError as e:
            self.logger.warning(f"LiteLLM Service Unavailable Error (will retry): {e}")
            raise APIConnectionError(f"Service unavailable: {e}") from e
        
        # Non-retriable errors (wrapped for consistency)
        except exceptions.AuthenticationError as e:
            self.logger.error(f"LiteLLM Authentication Error (non-retriable): {e}")
            raise APIAuthenticationError(f"Authentication failed: {e}") from e
        except exceptions.NotFoundError as e:
            self.logger.error(f"LiteLLM Not Found Error (non-retriable): {e}")
            raise APINotFoundError(f"Model or resource not found: {e}") from e
        except exceptions.InvalidRequestError as e:
                self.logger.error(f"LiteLLM Invalid Request Error (non-retriable): {e}")
                raise APIConfigurationError(f"Invalid request: {e}") from e
        except Exception as e:
            # Catch any other litellm or general error
            self.logger.error(f"LiteLLM non-retriable error: {e}", exc_info=True)
            raise APIError(f"An unexpected API error occurred: {e}") from e
        # --- END: MODIFIED SECTION ---

    # --- NEW HELPER METHOD ---
    def _get_completion_kwargs(self, provider_id: str, model_name: str, messages: List[Dict[str, str]], system_prompt: str) -> Dict[str, Any]:
        """Builds the kwargs dictionary for a litellm.completion call."""
        if not provider_id or not model_name:
            self.logger.error("No provider or model specified for kwargs.")
            # --- MODIFIED: Raise custom exception ---
            raise APIConfigurationError("Provider and model must be specified.")
        
        models_config = self.config.get_config("models_config.json")
        provider_config = models_config.get("providers", {}).get(provider_id, {})
        api_key = provider_config.get("api_key")
        base_url = provider_config.get("base_url")

        full_model_name = f"{provider_id}/{model_name}"
        self.logger.info(f"Preparing call for model: {full_model_name}")

        llm_messages = [{"role": "system", "content": system_prompt}] + messages
        kwargs = {
            "model": full_model_name,
            "messages": llm_messages,
            "stream": True,
        }
        
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["api_base"] = base_url
            
        return kwargs

    # --- NEW HELPER METHOD ---
    def _process_stream(self, response_stream: Iterator) -> Generator[str, None, None]:
        """Processes a litellm.completion stream and yields content."""
        for chunk in response_stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    # --- UPDATED SECTION ---
    # This function now implements fallback logic for RateLimitErrors.
    def chat_stream(self, messages: List[Dict[str, str]], system_prompt: str) -> Generator[str, None, None]:
        """
        Calls the active LLM using LiteLLM and streams the response.
        Includes fallback logic for RateLimitErrors.
        """
        
        models_config = self.config.get_config("models_config.json")
        active_provider = models_config.get("active_provider")
        active_model = models_config.get("active_model")
        
        try:
            # --- 1. First attempt with active provider ---
            if not active_provider or not active_model:
                self.logger.error("No active provider or model configured.")
                yield "Error: No active provider or model is configured in settings."
                return

            kwargs = self._get_completion_kwargs(
                active_provider, active_model, messages, system_prompt
            )
            response_stream = self._completion_with_retry(**kwargs)
            yield from self._process_stream(response_stream)
            
        # --- MODIFIED: Catch our custom APIRateLimitError ---
        except APIRateLimitError as e:
            # --- 2. Fallback on RateLimitError ---
            self.logger.warning(
                f"Rate limit error with {active_provider}/{active_model} (Error: {e}). "
                "Attempting fallback."
            )
            
            fallback_provider = models_config.get("fallback_provider")
            fallback_model = models_config.get("fallback_model")
            
            if not fallback_provider or not fallback_model:
                self.logger.error("Rate limit hit, but no fallback provider/model configured.")
                yield "Error: API rate limit exceeded. No fallback is configured."
                return

            try:
                # --- 3. Attempt with fallback provider ---
                self.logger.info(f"Using fallback: {fallback_provider}/{fallback_model}")
                fallback_kwargs = self._get_completion_kwargs(
                    fallback_provider, fallback_model, messages, system_prompt
                )
                fallback_stream = self._completion_with_retry(**fallback_kwargs)
                yield from self._process_stream(fallback_stream)
                
            # --- MODIFIED: Catch our base APIError ---
            except APIError as fallback_e:
                # --- 4. Fallback attempt failed ---
                self.logger.error(
                    f"Fallback attempt with {fallback_provider}/{fallback_model} failed: {fallback_e}",
                    exc_info=True
                )
                yield f"Error: Primary model rate limited. Fallback failed. ({type(fallback_e).__name__})"
            except Exception as fallback_e:
                self.logger.error(f"Unexpected fallback error: {fallback_e}", exc_info=True)
                yield f"Error: Primary model rate limited. Fallback failed. ({type(fallback_e).__name__})"
        
        # --- START: MODIFIED SECTION ---
        # Catch our specific custom exceptions
        except APIAuthenticationError as e:
            self.logger.error(f"API Authentication Error: {e}", exc_info=True)
            yield "Error: API Key Error. Check settings."
        except APIConnectionError as e:
            self.logger.error(f"API Connection Error: {e}", exc_info=True)
            yield "Error: Connection Error. Is Ollama running?"
        except APINotFoundError as e:
            model_str = f"{active_provider}/{active_model}" if active_provider else 'model'
            self.logger.error(f"API Not Found Error: {e}", exc_info=True)
            yield f"Error: Model '{model_str}' not found."
        except APIConfigurationError as e:
            self.logger.error(f"API Configuration Error: {e}", exc_info=True)
            yield f"Error: API Configuration Error. {e}"
        except APIError as e: # Catch-all for other API errors
            self.logger.error(f"LiteLLM API error after all retries: {e}", exc_info=True)
            yield f"Error: {type(e).__name__}. Failed to connect to model."
        except Exception as e:
            # --- 5. Handle all other primary errors ---
            self.logger.error(f"Unexpected error in chat_stream: {e}", exc_info=True)
            yield f"Error: An unexpected error occurred. {type(e).__name__}"
        # --- END: MODIFIED SECTION ---

    # --- UPDATED SECTION ---
    # This function now correctly handles api_key vs api_base
    # and constructs the full model name.
    # NOTE: No changes needed here. This function *handles* exceptions
    # by publishing events, it doesn't propagate them.
    # So it should catch the specific litellm exceptions directly.
    async def on_test_connection(self, provider: str, **kwargs):
        """Event handler for testing an API connection."""
        self.logger.info(f"Received test connection request for {provider}")
        
        # Get data from the event
        test_model = kwargs.get("model") # e.g., "llama3"
        api_key_or_url = kwargs.get("value") # The key or URL from the settings text box
        
        # --- START: This is the new logic ---
        # Construct the full model name (e.g., "ollama/llama3")
        full_test_model = f"{provider}/{test_model}"

        if not test_model:
            self.logger.error(f"No test model selected for provider: {provider}")
            await self.events.publish(
                "NOTIFICATION_EVENT.ERROR", 
                title=f"{provider} Test", 
                message="No model selected for this provider."
            )
            await self.events.publish(
                "API_EVENT.TEST_CONNECTION_RESULT", 
                provider=provider, 
                success=False
            )
            return

        success = False 
        
        # Build kwargs for the test call
        test_kwargs = {
            "model": full_test_model,
            "messages": [{"role": "user", "content": "Test"}],
            "max_tokens": 10,
        }

        # Determine if the value is a key or a base_url
        if provider == "ollama":
            test_kwargs["api_base"] = api_key_or_url
        else:
            test_kwargs["api_key"] = api_key_or_url
        # --- END: New logic ---
            
        try:
            # Run the synchronous test call in an async thread
            await asyncio.to_thread(
                litellm.completion,
                **test_kwargs # Pass the prepared kwargs
            )
            
            success = True
            self.logger.info(f"LiteLLM connection test successful for: {full_test_model}")
            await self.events.publish(
                "NOTIFICATION_EVENT.INFO",
                title=f"{provider.title()} Test",
                message="Connection successful!"
            )
            
        except exceptions.AuthenticationError as e:
            self.logger.error(f"LiteLLM AuthenticationError for {full_test_model}: {e}")
            await self.events.publish(
                "NOTIFICATION_EVENT.ERROR",
                title=f"{provider.title()} Test",
                message="Authentication FAILED. Check your API key."
            )
        except exceptions.APIConnectionError as e:
            self.logger.error(f"LiteLLM APIConnectionError for {full_test_model}: {e}")
            await self.events.publish(
                "NOTIFICATION_EVENT.ERROR",
                title=f"{provider.title()} Test",
                message="Connection FAILED. Check the server address and your network."
            )
        except exceptions.RateLimitError as e:
            self.logger.error(f"LiteLLM RateLimitError for {full_test_model}: {e}")
            await self.events.publish(
                "NOTIFICATION_EVENT.ERROR",
                title=f"{provider.title()} Test",
                message="Rate limit exceeded. Please try again later."
            )
        except exceptions.NotFoundError as e:
            self.logger.error(f"LiteLLM NotFoundError for {full_test_model}: {e}")
            await self.events.publish(
                "NOTIFICATION_EVENT.ERROR",
                title=f"{provider.title()} Test",
                message=f"Model '{test_model}' not found."
            )
        except Exception as e:
            self.logger.error(f"LiteLLNetwork connection test failed for {full_test_model}: {e}")
            await self.events.publish(
                "NOTIFICATION_EVENT.ERROR",
                title=f"{provider.title()} Test",
                message=f"An unexpected error occurred. Error: {str(e)[:100]}..."
            )
        
        finally:
            # Publish the final result (True or False) back to the SettingsWindow
            self.logger.debug(f"Publishing test result for {provider}: {success}")
            await self.events.publish(
                "API_EVENT.TEST_CONNECTION_RESULT", 
                provider=provider, 
                success=success
            )