import os
import logging
import asyncio
import litellm
from litellm import exceptions # <-- NEW
from tenacity import retry, stop_after_attempt, wait_exponential # <-- NEW
from typing import List, Dict, Generator, Optional, Iterator, Any
from core.service_locator import locator
from core.event_dispatcher import EventDispatcher
from utils.config_loader import ConfigLoader

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
        reraise=True
    )
    def _completion_with_retry(self, **kwargs) -> Any:
        """Internal synchronous call to litellm.completion with retries."""
        self.logger.debug(f"Attempting litellm.completion for model: {kwargs.get('model')}")
        try:
            return litellm.completion(**kwargs)
        except exceptions.APIConnectionError as e:
            self.logger.warning(f"LiteLLM API Connection Error (will retry): {e}")
            raise
        except exceptions.RateLimitError as e:
            self.logger.warning(f"LiteLLM Rate Limit Error (will retry): {e}")
            raise
        except exceptions.ServiceUnavailableError as e:
            self.logger.warning(f"LiteLLM Service Unavailable Error (will retry): {e}")
            raise
        except Exception as e:
            self.logger.error(f"LiteLLM non-retriable error: {e}", exc_info=True)
            raise

    # --- UPDATED SECTION ---
    # This function now loads all required config to make the API call.
    def chat_stream(self, messages: List[Dict[str, str]], system_prompt: str) -> Generator[str, None, None]:
        """
        Calls the active LLM using LiteLLM and streams the response.
        """
        
        # --- START: This is the new logic you need ---
        try:
            # 1. Load all necessary configs
            models_config = self.config.get_config("models_config.json")
            provider_id = models_config.get("active_provider")
            model_name = models_config.get("active_model")

            if not provider_id or not model_name:
                self.logger.error("No active provider or model configured.")
                yield "Error: No active provider or model is configured in settings."
                return

            # 2. Get the specific provider's details
            provider_config = models_config.get("providers", {}).get(provider_id, {})
            api_key = provider_config.get("api_key")
            base_url = provider_config.get("base_url")

            # 3. Construct the full model name for LiteLLM
            full_model_name = f"{provider_id}/{model_name}"
            
            self.logger.info(f"Connecting to LiteLLM with model: {full_model_name}")

            # 4. Build the kwargs for LiteLLM
            llm_messages = [{"role": "system", "content": system_prompt}] + messages
            kwargs = {
                "model": full_model_name,
                "messages": llm_messages,
                "stream": True,
            }
            
            # 5. Add the API key *if* it exists
            if api_key:
                kwargs["api_key"] = api_key
            
            # 6. Add base_url *if* it exists (for Ollama)
            if base_url:
                kwargs["api_base"] = base_url
            
            # --- END: New logic ---

            # Use the retry-wrapped function
            response_stream = self._completion_with_retry(**kwargs)
            
            for chunk in response_stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
                    
        except Exception as e:
            self.logger.error(f"LiteLLM API error after all retries: {e}", exc_info=True)
            error_message = f"Error: {type(e).__name__}. "
            if isinstance(e, exceptions.AuthenticationError):
                error_message += "API Key Error. Check settings."
            elif isinstance(e, exceptions.APIConnectionError):
                error_message += "Connection Error. Is Ollama running?"
            elif isinstance(e, exceptions.RateLimitError):
                error_message += "API Rate Limit Exceeded."
            elif isinstance(e, exceptions.NotFoundError):
                # Use full_model_name if it exists, otherwise log generic error
                model_str = 'model'
                if 'full_model_name' in locals():
                    model_str = full_model_name
                error_message += f"Model '{model_str}' not found."
            else:
                error_message += "Failed to connect to model."
            yield error_message

    # --- UPDATED SECTION ---
    # This function now correctly handles api_key vs api_base
    # and constructs the full model name.
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