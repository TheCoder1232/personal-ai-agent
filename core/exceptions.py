# file: core/exceptions.py
"""
Defines the custom exception hierarchy for the application.
"""

class AIAgentError(Exception):
    """Base exception for all application-specific errors."""
    pass

# --- Configuration Errors ---
class ConfigurationError(AIAgentError):
    """Error related to loading, parsing, or validating configuration."""
    pass

# --- Plugin Errors ---
class PluginError(AIAgentError):
    """Base error for plugin-related issues."""
    pass

class PluginLoadError(PluginError):
    """Error related to loading or initializing a plugin."""
    pass
    
class PluginExecutionError(PluginError):
    """Error raised during the execution of a plugin's method."""
    pass

# --- API Errors ---
class APIError(AIAgentError):
    """Base error for external API-related issues."""
    pass

class APIConnectionError(APIError):
    """Wraps connection-related errors from the API library."""
    pass
    
class APIAuthenticationError(APIError):
    """Wraps authentication-related errors from the API library."""
    pass
    
class APIRateLimitError(APIError):
    """Wraps rate limit errors from the API library."""
    pass
    
class APINotFoundError(APIError):
    """Wraps resource not found errors from the API library."""
    pass
    
class APIConfigurationError(APIError):
    """Error related to missing or invalid API configuration."""
    pass