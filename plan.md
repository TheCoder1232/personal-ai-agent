# Personal AI Agent - Complete Implementation Plan

## Architecture Overview

Plugin-based, event-driven architecture with dependency injection for maximum extensibility and maintainability.

### Core Architectural Components

1. **Plugin System** - Dynamic feature loading from `/plugins/` folder
2. **Event Dispatcher** - Comprehensive event bus for component communication
3. **Service Locator** - Full DI container for dependency management
4. **Context Manager** - Short-term memory with automatic summarization
5. **Role-Based System** - Automatic prompt selection based on LLM classification

## Technology Stack (Free Options)

### Core Framework

- Python 3.10+ with CustomTkinter for modern UI
- pystray (system tray), pynput (global hotkeys)
- asyncio for async operations

### AI & APIs

- Google Gemini API (free tier: 15 req/min, 1500/day)
- Ollama (local, completely free)
- OpenRouter (pay-per-use backup)

### Key Libraries

- `customtkinter` - Modern UI framework
- `pystray` + `Pillow` - System tray integration
- `pynput` - Global hotkey management
- `mcp` - Model Context Protocol SDK
- `google-generativeai` - Gemini API client
- `requests` - API calls
- `mss` - Fast screenshot capture
- `tkhtmlview` - Markdown rendering in chat

## Project Structure

```
personal-ai-agent/
├── main.py                          # Entry point, initializes DI container
├── core/
│   ├── service_locator.py          # Full DI container implementation
│   ├── event_dispatcher.py         # Comprehensive event bus
│   ├── plugin_manager.py           # Dynamic plugin loader
│   ├── context_manager.py          # Conversation memory with summarization
│   ├── agent.py                    # Unified agent (not multi-agent yet)
│   ├── api_manager.py              # Multi-model API abstraction
│   ├── command_executor.py         # Safe tool execution with timeout
│   └── role_selector.py            # LLM-based role classification
├── plugins/
│   ├── __init__.py
│   ├── screen_capture.py           # Screen capture plugin
│   ├── mcp_integration.py          # MCP plugin
│   └── [future plugins]            # Easy to extend
├── config/
│   ├── ui_config.json              # Window positions, theme, sizes
│   ├── models_config.json          # API keys, model list
│   ├── mcp_config.json             # MCP server configurations
│   ├── system_config.json          # Logging, hotkeys, general settings
│   └── prompts/
│       ├── roles.json              # Role definitions and system prompts
│       └── classification.json     # Role selection prompt
├── ui/
│   ├── tray_manager.py             # System tray with minimize support
│   ├── popup_window.py             # Chat window with markdown rendering
│   ├── settings_window.py          # Multi-tab settings with test buttons
│   └── notification.py             # Unified notification system
├── utils/
│   ├── logger.py                   # Comprehensive logging
│   ├── config_loader.py            # Multi-file config management
│   └── safety.py                   # Subprocess/timeout helpers
└── assets/
    └── icons/                      # UI icons
```

## Phase 1: Core Architecture & Plugin System

**Goal**: Build the foundational architecture with DI container, event system, and plugin loader

### Tasks:

1. **Dependency Injection Container** (`core/service_locator.py`):

   - Implement service registration/resolution
   - Support singleton and transient lifetimes
   - Constructor injection support
   - Service factory pattern for complex initialization

2. **Event Dispatcher** (`core/event_dispatcher.py`):

   - Comprehensive event bus with subscribe/publish
   - Event types: `UI_EVENT`, `API_EVENT`, `PLUGIN_EVENT`, `TOOL_EVENT`, `ERROR_EVENT`, `NOTIFICATION_EVENT`
   - Async event handling support
   - Event filtering and priority queues

3. **Plugin Manager** (`core/plugin_manager.py`):

   - Auto-discover Python modules in `/plugins/` folder
   - Plugin base class with lifecycle hooks (init, start, stop, cleanup)
   - Plugin metadata (name, version, dependencies, required_services)
   - Load all plugins at startup automatically
   - Plugin enable/disable via settings

4. **Multi-Config System** (`utils/config_loader.py`):

   - Load/save 4 separate JSON configs: `ui_config.json`, `models_config.json`, `mcp_config.json`, `system_config.json`
   - Auto-create defaults if missing
   - Config validation and migration support
   - Watch for file changes (optional hot-reload)

5. **Logging System** (`utils/logger.py`):

   - Rotating file logs to `%APPDATA%/PersonalAIAgent/logs/`
   - Structured logging with context (component name, event IDs)
   - Log levels: DEBUG, INFO, WARNING, ERROR
   - Log all events from event dispatcher
   - Separate log files per component (ui.log, api.log, plugins.log, errors.log)

**Deliverable**: Working DI container, event system, plugin loader, and config system

## Phase 2: UI Foundation & Basic Features

**Goal**: System tray app, settings window, chat popup with markdown support

### Tasks:

1. **System Tray Manager** (`ui/tray_manager.py`):

   - Launch to tray on startup
   - Left-click: restore minimized chat window (if minimized) or open settings
   - Right-click menu: "Open Chat", "Settings", "Quit"
   - Subscribe to `UI_EVENT.MINIMIZE_TO_TRAY` event
   - Remember if chat window was open before minimize

2. **Settings Window** (`ui/settings_window.py`):

   - Tabbed interface: Models, API Keys, Hotkeys, MCP Servers, Plugins, Logs
   - **Models Tab**: Dropdown to select Gemini/Ollama/OpenRouter, model list
   - **API Keys Tab**: Input fields with "Test Connection" buttons
     - Gemini: Validate key with test API call
     - OpenRouter: Validate key with test API call
     - Ollama: Check if running, list available models
   - **Hotkeys Tab**: Configurable hotkeys with conflict detection
   - **Plugins Tab**: List discovered plugins with enable/disable toggles
   - Load/save to respective config files
   - Emit `UI_EVENT.SETTINGS_CHANGED` on save

3. **Popup Chat Window** (`ui/popup_window.py`):

   - 400x600px default, resizable, always on top when focused
   - Chat history with `tkhtmlview` for markdown rendering
   - Text input box with send button
   - Loading indicator during API calls
   - "Minimize to Tray" button (not close)
   - Remember position in `ui_config.json`
   - Subscribe to `API_EVENT.RESPONSE_CHUNK` for streaming
   - Tool name highlighting (e.g., "Would you like to use **FileSearch**?")

4. **Global Hotkey Manager** (`input/hotkey_manager.py` - not a plugin yet):

   - Use `pynput.keyboard.GlobalHotKeys`
   - Default: Ctrl+Shift+Space (open chat), Ctrl+Shift+X (capture screen)
   - Emit events: `UI_EVENT.OPEN_CHAT`, `PLUGIN_EVENT.SCREEN_CAPTURE`
   - Load hotkey config from `system_config.json`

5. **Unified Notification System** (`ui/notification.py`):

   - CustomTkinter overlay window for all notifications
   - Types: Tool Approval, Background Updates, Completion Summaries, Warnings, Errors
   - Tool Approval: Show tool name, description, args, "Approve"/"Reject", 30s timeout
   - Background Updates: Progress bars, status messages (non-blocking)
   - Subscribe to: `TOOL_EVENT.APPROVAL_NEEDED`, `NOTIFICATION_EVENT.*`, `ERROR_EVENT.*`

**Deliverable**: Fully functional UI with tray, settings, chat window, hotkeys, notifications

## Phase 3: AI Core & Multi-Model Support

**Goal**: Working chat with Gemini/Ollama/OpenRouter, role-based prompts, context management

### Tasks:

1. **API Manager** (`core/api_manager.py`):

   - Abstract `BaseAPI` class with methods: `chat()`, `chat_stream()`, `supports_vision()`
   - `GeminiAPI`, `OllamaAPI`, `OpenRouterAPI` implementations
   - Load config from `models_config.json`
   - Emit events: `API_EVENT.REQUEST_START`, `API_EVENT.RESPONSE_CHUNK`, `API_EVENT.REQUEST_COMPLETE`, `API_EVENT.ERROR`
   - Auto-detect Ollama models on startup

2. **Context Manager** (`core/context_manager.py`):

   - Store last 50+ messages in memory
   - Automatic summarization of older messages (beyond 20 most recent)
   - Use LLM to generate summary: "Previous conversation summary: ..."
   - Inject summarized context into system prompt
   - Methods: `add_message()`, `get_context()`, `clear()`, `get_summary()`
   - Registered as singleton service in DI container

3. **Role Selector** (`core/role_selector.py`):

   - Load role definitions from `config/prompts/roles.json`
   - Roles: General, Coding, FileOps, WebSearch, Creative, Analysis
   - Pre-query classification: send user message to LLM with classification prompt
   - Uses fast/cheap model (Gemini Flash) for classification
   - Cache classification for conversation (don't re-classify each message)
   - Emit `API_EVENT.ROLE_SELECTED` event
   - Inject selected role's system prompt into agent

4. **Agent Core** (`core/agent.py`):

   - Unified agent class (not multi-agent yet)
   - Depends on: `APIManager`, `ContextManager`, `RoleSelector`, `EventDispatcher`
   - Main method: `async process_query(user_message, image_data=None)`
   - Flow:

     1. Select role via `RoleSelector`
     2. Get context from `ContextManager`
     3. Build prompt with role + context + available tools
     4. Stream response from `APIManager`
     5. Parse tool requests, emit `TOOL_EVENT.EXECUTION_REQUESTED`
     6. Update context with response

   - Subscribe to: `TOOL_EVENT.EXECUTION_COMPLETE` to include results in next prompt

**Deliverable**: Working chat with all models, automatic role selection, conversation memory

## Phase 4: Plugin Implementation (Screen Capture & MCP)

**Goal**: Implement core features as plugins

### Tasks:

1. **Screen Capture Plugin** (`plugins/screen_capture.py`):

   - Inherits from `PluginBase`
   - Required services: `EventDispatcher`, `ConfigLoader`
   - Uses `mss` library for fast screenshot
   - Subscribe to: `PLUGIN_EVENT.SCREEN_CAPTURE`, `UI_EVENT.POPUP_OPENED` (if auto-capture enabled)
   - Resize large images (max 2000px width)
   - Encode to base64, emit `PLUGIN_EVENT.SCREEN_CAPTURED` with image data
   - No storage (discard after use)
   - Settings: auto-capture on popup, monitor selection

2. **MCP Integration Plugin** (`plugins/mcp_integration.py`):

   - Inherits from `PluginBase`
   - Required services: `EventDispatcher`, `ConfigLoader`, `CommandExecutor`
   - Subcomponents:
     - `MCPClient` - Connect to servers via stdio transport
     - `MCPManager` - Manage multiple server connections
     - `ToolRegistry` - Unified tool catalog
   - On init: Connect to enabled servers from `mcp_config.json`
   - Tool discovery: Call `list_tools()` on all servers
   - Subscribe to: `TOOL_EVENT.EXECUTION_REQUESTED`
   - Parse tool calls from LLM, emit `TOOL_EVENT.APPROVAL_NEEDED`
   - After approval: Execute via `CommandExecutor`, emit `TOOL_EVENT.EXECUTION_COMPLETE`

3. **Command Executor** (`core/command_executor.py`):

   - Safe subprocess execution with timeout (default 30s)
   - Each MCP tool call runs in subprocess/thread
   - Capture stdout/stderr safely
   - Kill subprocess on timeout
   - Safety checks: Warn on dangerous operations (file deletion, network calls)
   - Emit events: `TOOL_EVENT.STARTED`, `TOOL_EVENT.OUTPUT`, `TOOL_EVENT.COMPLETE`, `TOOL_EVENT.TIMEOUT`

**Deliverable**: Screen capture and MCP fully working as dynamically loaded plugins

## Phase 5: Polish, Safety & Production Readiness

**Goal**: Error handling, UI polish, comprehensive testing

### Tasks:

1. **Safety Layer Enhancements** (`utils/safety.py`):

   - Subprocess isolation helpers
   - Timeout enforcement
   - Resource limits (memory, CPU)
   - Logging all tool executions with full context

2. **Comprehensive Error Handling**:

   - API failures: Retry with exponential backoff, fallback to different model
   - MCP server crashes: Auto-restart, notify user
   - Plugin failures: Disable plugin, log error, continue running
   - Network errors: Queue requests, offline mode detection
   - All errors emit `ERROR_EVENT.*` for centralized handling

3. **UI Improvements**:

   - Dark/light mode toggle
   - Window position/size persistence
   - Chat history search
   - Export conversation to markdown
   - Smooth animations for notifications
   - Keyboard shortcuts in chat (Ctrl+Enter to send)

4. **Testing & Validation**:

   - Test all API connections
   - Test plugin loading/unloading
   - Test event system under load
   - Test context summarization
   - Test role classification accuracy

5. **Documentation**:

   - README.md with setup instructions
   - Plugin development guide
   - Configuration file documentation
   - MCP server recommendations (filesystem, github, brave-search)
   - Troubleshooting guide

**Deliverable**: Production-ready personal AI agent

## Key Design Patterns Used

1. **Plugin Pattern**: Dynamic feature loading without modifying core
2. **Dependency Injection**: Loose coupling, easy testing, clear dependencies
3. **Observer Pattern (Events)**: Decoupled communication between components
4. **Strategy Pattern**: Interchangeable API providers
5. **Singleton Pattern**: Shared services (EventDispatcher, ContextManager)
6. **Factory Pattern**: Plugin instantiation, API provider creation

## Configuration Files Structure

### `ui_config.json`

```json
{
  "theme": "system",
  "popup": {"x": 100, "y": 100, "width": 400, "height": 600},
  "minimize_to_tray": true,
  "markdown_rendering": true
}
```

### `models_config.json`

```json
{
  "active_provider": "gemini",
  "active_model": "gemini-2.0-flash-exp",
  "providers": {
    "gemini": {"api_key": "", "models": [...]},
    "ollama": {"base_url": "http://localhost:11434", "models": []},
    "openrouter": {"api_key": "", "models": [...]}
  }
}
```

### `mcp_config.json`

```json
{
  "servers": [
    {
      "id": "filesystem",
      "name": "File System",
      "command": "python",
      "args": ["-m", "mcp_server_filesystem"],
      "enabled": true
    }
  ]
}
```

### `system_config.json`

```json
{
  "hotkeys": {
    "open_chat": "<ctrl>+<shift>+<space>",
    "screen_capture": "<ctrl>+<shift>+x"
  },
  "logging": {"level": "INFO", "save_conversations": false},
  "context": {"max_messages": 50, "summarize_threshold": 20}
}
```

### `config/prompts/roles.json`

```json
{
  "roles": [
    {
      "id": "general",
      "name": "General Assistant",
      "keywords": ["help", "what", "how", "explain"],
      "system_prompt": "You are a helpful AI assistant..."
    },
    {
      "id": "coding",
      "name": "Coding Assistant",
      "keywords": ["code", "function", "debug", "program"],
      "system_prompt": "You are an expert programming assistant..."
    }
  ]
}
```

## Event System Schema

### Event Types:

- `UI_EVENT`: `OPEN_CHAT`, `MINIMIZE_TO_TRAY`, `SETTINGS_CHANGED`, `POPUP_OPENED`
- `API_EVENT`: `REQUEST_START`, `RESPONSE_CHUNK`, `REQUEST_COMPLETE`, `ERROR`, `ROLE_SELECTED`
- `PLUGIN_EVENT`: `LOADED`, `STARTED`, `STOPPED`, `SCREEN_CAPTURE`, `SCREEN_CAPTURED`
- `TOOL_EVENT`: `EXECUTION_REQUESTED`, `APPROVAL_NEEDED`, `EXECUTION_COMPLETE`, `STARTED`, `OUTPUT`, `TIMEOUT`
- `NOTIFICATION_EVENT`: `INFO`, `WARNING`, `ERROR`, `UPDATE`, `SUMMARY`
- `ERROR_EVENT`: `API_FAILURE`, `PLUGIN_CRASH`, `MCP_ERROR`, `NETWORK_ERROR`

## Plugin Development Guide

Every plugin must:

1. Inherit from `PluginBase`
2. Implement: `get_metadata()`, `initialize()`, `start()`, `stop()`
3. Declare required services via dependency injection
4. Use event system for all communication
5. Handle errors gracefully

Example plugin structure:

```python
class MyPlugin(PluginBase):
    def __init__(self, event_dispatcher, config_loader):
        self.events = event_dispatcher
        self.config = config_loader
    
    def get_metadata(self):
        return {"name": "MyPlugin", "version": "1.0"}
    
    def initialize(self):
        self.events.subscribe("MY_EVENT", self.handler)
    
    def start(self): pass
    def stop(self): pass
```

## Estimated Timeline

- **Phase 1** (Architecture): ~4-5 days (DI container, event system, plugin loader)
- **Phase 2** (UI): ~3-4 days (tray, windows, settings, notifications, markdown)
- **Phase 3** (AI Core): ~4-5 days (API manager, context, role selector, agent)
- **Phase 4** (Plugins): ~3-4 days (screen capture, MCP integration)
- **Phase 5** (Polish): ~2-3 days (error handling, testing, docs)

**Total**: ~2-3 weeks of focused development

## Learning Resources

Since you chose "Basic OOP, willing to learn" (6b):

- Dependency Injection: Start with simple service locator, add features as needed
- Event System: Begin with basic pub/sub, expand to comprehensive bus
- Plugin System: Follow provided examples, copy pattern for new plugins
- We'll implement these patterns gradually with comments and explanations