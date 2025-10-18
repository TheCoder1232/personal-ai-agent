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

    def load_provider_config(self):
        """Loads provider settings from the config file."""
        models_config = self.config.get_config("models_config.json")
        providers = models_config.get("providers", {})
        
        # Set the base_url for Ollama
        ollama_url = providers.get("ollama", {}).get("base_url")
        if ollama_url:
            # Prefer using setattr to avoid static type/attribute errors if the module
            # doesn't declare api_base_for; this creates the attribute at runtime.
            setattr(litellm, "api_base_for", {"ollama": ollama_url})
            self.logger.info(f"Ollama base URL set for LiteLLM: {ollama_url}")

    def get_active_model(self) -> str:
        """Gets the active model string from config."""
        return self.config.get("models_config.json", "active_model", "gemini/gemini-1.5-flash")

    # --- NEW: Decorator for retry logic ---
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10), # 2s, 4s, 8s, 10s
        stop=stop_after_attempt(4),
        reraise=True # Re-raise the final exception
    )
    def _completion_with_retry(self, **kwargs) -> Any:
        """Internal synchronous call to litellm.completion with retries."""
        self.logger.debug(f"Attempting litellm.completion for model: {kwargs.get('model')}")
        try:
            return litellm.completion(**kwargs)
        except exceptions.APIConnectionError as e:
            self.logger.warning(f"LiteLLM API Connection Error (will retry): {e}")
            raise # Re-raise to trigger retry
        except exceptions.RateLimitError as e:
            self.logger.warning(f"LiteLLM Rate Limit Error (will retry): {e}")
            raise # Re-raise to trigger retry
        except exceptions.ServiceUnavailableError as e:
            self.logger.warning(f"LiteLLM Service Unavailable Error (will retry): {e}")
            raise # Re-raise to trigger retry
        except Exception as e:
            self.logger.error(f"LiteLLM non-retriable error: {e}", exc_info=True)
            raise # Re-raise but don't retry

    def chat_stream(self, messages: List[Dict[str, str]], system_prompt: str) -> Generator[str, None, None]:
        """
        Calls the active LLM using LiteLLM and streams the response.
        """
        model = self.get_active_model()
        llm_messages = [{"role": "system", "content": system_prompt}] + messages
        self.logger.info(f"Connecting to LiteLLM with model: {model}")
        
        try:
            # --- MODIFIED: Use the retry-wrapped function ---
            response_stream = self._completion_with_retry(
                model=model,
                messages=llm_messages,
                stream=True
            )
            
            for chunk in response_stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
                    
        except Exception as e:
            self.logger.error(f"LiteLLM API error after all retries: {e}", exc_info=True)
            # --- MODIFIED: Better error messages ---
            error_message = f"Error: {type(e).__name__}. "
            if isinstance(e, exceptions.AuthenticationError):
                error_message += "API Key Error. Check settings."
            elif isinstance(e, exceptions.APIConnectionError):
                error_message += "Connection Error. Is Ollama running?"
            elif isinstance(e, exceptions.RateLimitError):
                error_message += "API Rate Limit Exceeded."
            elif isinstance(e, exceptions.NotFoundError):
                error_message += f"Model '{model}' not found."
            else:
                error_message += "Failed to connect to model."
            yield error_message

    async def on_test_connection(self, provider: str):
        """Event handler for testing an API connection."""
        self.logger.info(f"Received test connection request for {provider}")
        
        # We need a representative model for the provider
        models_config = self.config.get("models_config.json", "providers", {}).get(provider, {})
        test_model = models_config.get("models", [None])[0]
        
        if not test_model:
            self.logger.error(f"No test model found for provider: {provider}")
            await self.events.publish("NOTIFICATION_EVENT.ERROR", title=f"{provider} Test", message="No model configured for this provider.")
            return

        try:
            # Run the synchronous test call in an async thread
            await asyncio.to_thread(
                litellm.completion,
                model=test_model,
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=10
            )
            
            # If it doesn't throw an exception, it worked
            self.logger.info(f"LiteLLM connection test successful for: {test_model}")
            await self.events.publish(
                "NOTIFICATION_EVENT.INFO",
                title=f"{provider.title()} Test",
                message="Connection successful!"
            )
            
        except exceptions.AuthenticationError as e:
            self.logger.error(f"LiteLLM AuthenticationError for {test_model}: {e}")
            await self.events.publish(
                "NOTIFICATION_EVENT.ERROR",
                title=f"{provider.title()} Test",
                message="Authentication FAILED. Check your API key."
            )
        except exceptions.APIConnectionError as e:
            self.logger.error(f"LiteLLM APIConnectionError for {test_model}: {e}")
            await self.events.publish(
                "NOTIFICATION_EVENT.ERROR",
                title=f"{provider.title()} Test",
                message="Connection FAILED. Check the server address and your network."
            )
        except exceptions.RateLimitError as e:
            self.logger.error(f"LiteLLM RateLimitError for {test_model}: {e}")
            await self.events.publish(
                "NOTIFICATION_EVENT.ERROR",
                title=f"{provider.title()} Test",
                message="Rate limit exceeded. Please try again later."
            )
        except exceptions.NotFoundError as e:
            self.logger.error(f"LiteLLM NotFoundError for {test_model}: {e}")
            await self.events.publish(
                "NOTIFICATION_EVENT.ERROR",
                title=f"{provider.title()} Test",
                message=f"Model '{test_model}' not found."
            )
        except Exception as e:
            self.logger.error(f"LiteLLM connection test failed for {test_model}: {e}")
            await self.events.publish(
                "NOTIFICATION_EVENT.ERROR",
                title=f"{provider.title()} Test",
                message=f"An unexpected error occurred. Error: {str(e)[:100]}..."
            )