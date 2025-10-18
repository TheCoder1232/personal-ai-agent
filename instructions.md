# **Personal AI Agent - Detailed Project Plan**

## **Project Overview**
A locally-running AI assistant with voice and text capabilities, computer control via MCP, thinking visualization, and global hotkey access. Built with Python for Windows 11, featuring a modern UI that minimizes to system tray.

---

## **1. Technology Stack**

### **Core Framework**
- **Python 3.10+**: Main programming language
- **CustomTkinter**: Modern UI framework (clean, native-looking, easy to learn)
- **pystray**: System tray integration
- **pynput**: Global hotkey management

### **AI & API Integration**
- **OpenRouter API**: Multi-model access
- **Google Gemini API**: Direct Gemini integration  
- **Ollama**: Local model support
- **MCP Python SDK**: Model Context Protocol client

### **Audio Processing**
- **Whisper (local)**: Speech-to-text via faster-whisper or whisper.cpp Python bindings
- **PyAudio** or **sounddevice**: Audio capture

### **Screen Capture**
- **Pillow (PIL)**: Screenshot capture
- **mss**: Fast cross-platform screenshots
- **pyautogui**: Alternative for screen capture

### **Additional Libraries**
- **asyncio**: Async operations for MCP
- **threading**: Background task management
- **json**: Configuration management
- **logging**: Comprehensive logging system
- **base64**: Image encoding for API

---

## **2. Architecture Design**

### **2.1 Core Components**

```
personal-ai-agent/
│
├── main.py                    # Entry point, orchestrates everything
├── config/
│   ├── settings.json          # User settings (API keys, models, hotkeys)
│   ├── mcp_servers.json       # MCP server configurations
│   └── prompts.json           # System prompts library
│
├── core/
│   ├── agent.py               # Main AI agent logic
│   ├── thinking.py            # Thinking process manager
│   ├── api_manager.py         # Handles all API calls (Gemini/OpenRouter/Ollama)
│   └── command_executor.py    # Executes system commands with approval
│
├── mcp/
│   ├── mcp_client.py          # MCP client implementation
│   ├── mcp_manager.py         # Manages multiple MCP servers
│   └── tool_registry.py       # Registers and tracks available tools
│
├── ui/
│   ├── popup_window.py        # Main chat popup (CTk)
│   ├── settings_window.py     # Full settings UI (CTk)
│   ├── tray_manager.py        # System tray icon & menu
│   ├── notification.py        # Command confirmation notifications
│   └── thinking_display.py    # Thinking process UI component
│
├── input/
│   ├── hotkey_manager.py      # Global hotkey listener
│   ├── audio_capture.py       # Push-to-talk recording
│   ├── whisper_handler.py     # Local Whisper transcription
│   └── screen_capture.py      # Screenshot functionality
│
├── utils/
│   ├── logger.py              # Logging configuration
│   ├── config_loader.py       # Config file management
│   └── helpers.py             # Utility functions
│
└── assets/
    ├── icons/                 # Tray icons, UI icons
    └── whisper_model/         # Local Whisper model files
```

---

## **3. Detailed Feature Implementation**

### **3.1 System Tray & Window Management**

**Behavior:**
- App launches directly to system tray (no taskbar icon)
- Single tray icon click opens settings window
- Right-click shows menu: "Settings", "Quit"
- Popup window appears via hotkey, not from tray

**Implementation:**
```python
# pystray for tray icon
# CustomTkinter windows set to topmost
# Hide from taskbar: window.overrideredirect(True) or withdraw()
# Remember position: Save/load from settings.json
```

**Settings Window:**
- Tabbed interface (CustomTkinter CTkTabview)
- Tabs: Models, API Keys, System Prompts, Hotkeys, MCP Servers, Screen Context, Logs
- Modern card-based layout with CustomTkinter's built-in styling

---

### **3.2 Global Hotkeys**

**Hotkey Scheme:**
- **Ctrl+Shift+Space**: Open popup window (text chat)
- **Ctrl+Shift+V**: Push-to-talk (hold to record, release to process)
- **Ctrl+Shift+S**: Toggle screen context feature on/off
- **Ctrl+Shift+X**: Force capture screen and attach to next query

**Implementation:**
```python
# Use pynput.keyboard.GlobalHotKeys
# Run in separate daemon thread
# Thread-safe queue to communicate with main UI thread
# Configurable via settings UI
```

---

### **3.3 Popup Chat Window**

**Design:**
- Small, elegant window (400x600px default, resizable)
- Always on top when focused
- Minimizes to tray when loses focus
- Dark/light mode support (follows system or manual)

**Components:**
- Text input box at bottom (CustomTkinter CTkTextbox)
- Send button (icon-based)
- Chat history scrollable area (CustomTkinter CTkScrollableFrame)
- Thinking display section (collapsible)
- Screen context indicator (small badge when enabled)

**Thinking Display:**
- Shows thinking step titles in real-time as they arrive
- Each step is a collapsible card (CustomTkinter CTkFrame with toggle)
- Expand to see full thought content
- Different color for completed vs in-progress steps

---

### **3.4 AI Agent Core**

**Thinking Process:**
The agent uses a structured thinking loop inspired by chain-of-thought reasoning, where it breaks down complex requests into steps before generating responses

**Flow:**
1. User input received (text or transcribed audio)
2. **Think Phase**: Agent generates thinking steps
   - "Understanding user intent..."
   - "Checking available tools..."
   - "Planning approach..."
   - Each step streams to UI in real-time
3. **Tool Selection**: Determines if MCP tools needed
4. **Execution Phase**: Generates response or prepares commands
5. **Approval Phase** (if commands): Shows notification
6. **Response Phase**: Streams final answer to UI

**Implementation:**
```python
# Async architecture for non-blocking operations
# Thinking uses special system prompt
# Separate API call for thinking vs final response
# Stream results using SSE or polling
```

---

### **3.5 MCP Integration**

MCP (Model Context Protocol) is a standardized way for AI applications to connect with external tools and data sources through a client-server architecture

**MCP Client Setup:**
```python
# Use mcp Python SDK (pip install mcp)
# Connect to servers defined in mcp_servers.json
# Each server runs as subprocess (stdio transport)
```

**mcp_servers.json Structure:**
```json
{
  "servers": [
    {
      "name": "filesystem",
      "command": "python",
      "args": ["-m", "mcp_server_filesystem"],
      "env": {},
      "enabled": true
    },
    {
      "name": "github",
      "command": "node",
      "args": ["path/to/github-mcp-server"],
      "enabled": false
    }
  ]
}
```

**Tool Discovery:**
- On startup, connect to all enabled MCP servers
- Query each server for available tools using list_tools()
- Build unified tool registry
- Present to LLM in system prompt as available actions

**Tool Execution:**
- When LLM requests tool use, call the appropriate MCP server's call_tool() method with arguments
- All tool calls require user approval (see Command Confirmation)

---

### **3.6 Command Confirmation System**

**Windows Native Notifications:**
```python
# Use Windows 10 Toast Notifications (win10toast-click library)
# Or custom overlay window with CustomTkinter (more control)
```

**Notification Design:**
- Title: "Agent wants to execute command"
- Description: Plain English explanation (max 100 chars)
- Technical details: Expandable section with actual command
- Buttons: "✓ Approve" | "✗ Reject"
- Timeout: 30 seconds (auto-reject)

**Implementation:**
```python
# Block agent execution until user responds
# Use threading.Event for synchronization
# Queue system to handle multiple pending approvals
```

---

### **3.7 Audio Input (Push-to-Talk)**

**Whisper Model:**
- Use `faster-whisper` (optimized C++ implementation)
- Model size: Base or Small (good balance of speed/accuracy)
- Runs on CPU (GPU optional for faster transcription)
- Model auto-downloads on first run to `assets/whisper_model/`

**PTT Implementation:**
```python
# Hold Ctrl+Shift+V to record
# Show recording indicator in popup window
# On release, stop recording
# Transcribe with Whisper (show "Transcribing..." spinner)
# Send transcription to agent as text input
```

**Audio Capture:**
```python
# Use sounddevice for recording (simpler than PyAudio)
# Save to temporary WAV file
# Pass to faster-whisper for transcription
# Delete temp file after transcription
```

---

### **3.8 Screen Context Feature**

**Behavior:**
- Toggle on/off via hotkey or settings
- When enabled AND popup opened: automatically captures screen
- Captured image sent to LLM with query
- Small badge in popup shows "Screen context attached"

**Implementation:**
```python
# Use mss library for fast screenshot
# Capture primary monitor only (or all monitors based on settings)
# Resize large images (max 2000px width) to reduce API costs
# Encode to base64 for API transmission
# Vision-capable models like Gemini and GPT-4 Vision can analyze images
```

---

### **3.9 Multi-Model Support**

**API Manager Design:**
- Abstract API interface with unified methods
- Three implementations: GeminiAPI, OpenRouterAPI, OllamaAPI
- User selects active model in settings
- Settings stores: provider, model name, API key, base URL

**settings.json Structure:**
```json
{
  "active_model": {
    "provider": "gemini",
    "model": "gemini-2.0-flash-exp",
    "api_key": "YOUR_KEY_HERE"
  },
  "models": {
    "gemini": [
      {"name": "gemini-2.0-flash-exp", "supports_vision": true},
      {"name": "gemini-1.5-pro", "supports_vision": true}
    ],
    "openrouter": [
      {"name": "anthropic/claude-3.5-sonnet", "supports_vision": true},
      {"name": "google/gemini-pro-1.5", "supports_vision": true}
    ],
    "ollama": [
      {"name": "llama3.1:8b", "supports_vision": false},
      {"name": "llava", "supports_vision": true}
    ]
  }
}
```

**Ollama Auto-Detection:**
```python
# Ping Ollama API (default: http://localhost:11434)
# GET /api/tags to list installed models
# Populate settings automatically
```

---

### **3.10 System Prompts**

**Prompt Library:**
- Multiple system prompts for different use cases
- Stored in `config/prompts.json`
- Editable via settings UI
- Variables: `{thinking_enabled}`, `{tools_available}`, `{date}`, `{user_name}`

**Default Prompts:**
1. **Standard**: Helpful assistant with thinking
2. **Coding**: Programming-focused with code execution tools
3. **Research**: Web search and analysis focused
4. **Creative**: More open-ended, less structured

---

### **3.11 Logging System**

**Log Structure:**
```python
# Use Python's logging module
# Rotating file handler (max 10MB per file, keep 5 files)
# Logs saved to %APPDATA%/PersonalAIAgent/logs/
```

**Log Levels:**
- DEBUG: All events, thinking steps, API calls
- INFO: User actions, command executions
- WARNING: Failed operations, retries
- ERROR: Exceptions, crashes

**Log Contents:**
- Timestamp, level, component, message
- User queries and agent responses (optional, privacy toggle)
- MCP tool calls and results
- API call metadata (not full responses to save space)

---

## **4. Development Phases**

### **Phase 1: Foundation (Week 1)**
- Set up project structure
- Implement config system
- Create basic CustomTkinter UI (popup + settings windows)
- System tray integration with pystray
- Global hotkey manager with pynput

### **Phase 2: AI Core (Week 2)**
- API manager for Gemini/OpenRouter/Ollama
- Basic agent logic (no thinking yet)
- Text-based chat functionality
- Response streaming to UI
- Logging system

### **Phase 3: MCP Integration (Week 3)**
- Implement MCP client using the official Python SDK
- MCP server configuration and management
- Tool discovery and registry
- Command confirmation system
- Test with simple MCP servers

### **Phase 4: Advanced Features (Week 4)**
- Thinking process implementation
- Thinking display UI
- Screen capture integration
- Vision API support for models

### **Phase 5: Audio (Week 5)**
- Whisper integration (faster-whisper)
- Push-to-talk implementation
- Audio recording and playback
- UI indicators for recording state

### **Phase 6: Polish (Week 6)**
- Error handling improvements
- UI/UX refinements
- Settings persistence
- Comprehensive testing
- Documentation

---

## **5. Key Design Decisions**

### **Why CustomTkinter?**
CustomTkinter provides modern, fully customizable widgets that work consistently across Windows, macOS, and Linux, with built-in dark/light mode support. It's easier to learn than PyQt while looking far more modern than standard Tkinter.

### **Why pynput for hotkeys?**
pynput provides the GlobalHotKeys class that handles multiple global keyboard shortcuts reliably across platforms, and it's lightweight with minimal dependencies.

### **Why faster-whisper over OpenAI Whisper?**
Faster-whisper uses optimized C++ implementation (CTranslate2) providing 4x faster inference with lower memory usage while maintaining accuracy. Perfect for local deployment.

### **Why Windows notifications vs custom overlay?**
Start with CustomTkinter-based overlay window for full control over design, timeout behavior, and button actions. Windows Toast Notifications are unreliable for interactive buttons.

---

## **6. Configuration Files**

### **settings.json** (User Settings)
```json
{
  "version": "1.0",
  "ui": {
    "theme": "system",
    "popup_position": {"x": 100, "y": 100},
    "popup_size": {"width": 400, "height": 600}
  },
  "hotkeys": {
    "open_popup": "<ctrl>+<shift>+<space>",
    "push_to_talk": "<ctrl>+<shift>+v",
    "toggle_screen_context": "<ctrl>+<shift>+s",
    "force_screenshot": "<ctrl>+<shift>+x"
  },
  "models": { /* ... */ },
  "active_model": { /* ... */ },
  "screen_context": {
    "enabled": false,
    "auto_capture_on_popup": true,
    "max_image_width": 2000
  },
  "whisper": {
    "model_size": "base",
    "device": "cpu",
    "language": "en"
  },
  "logging": {
    "level": "INFO",
    "save_conversations": false
  }
}
```

### **mcp_servers.json** (MCP Configuration)
```json
{
  "version": "1.0",
  "servers": [
    {
      "id": "filesystem",
      "name": "File System",
      "description": "Read, write, and search local files",
      "command": "python",
      "args": ["-m", "mcp_server_filesystem", "--base-dir", "C:/Users/YourName"],
      "env": {},
      "enabled": true
    }
  ]
}
```

### **prompts.json** (System Prompts)
```json
{
  "prompts": [
    {
      "id": "default",
      "name": "Standard Assistant",
      "system_prompt": "You are a helpful AI assistant with access to system tools...",
      "thinking_enabled": true
    }
  ]
}
```

---

## **7. Security & Privacy Considerations**

1. **API Keys**: Store encrypted or in secure credential storage (consider keyring library)
2. **MCP Sandbox**: Warn users that MCP servers have system access
3. **Command Approval**: ALWAYS require approval for file operations, network calls, code execution
4. **Screen Capture**: Clear visual indicator when screen context is enabled
5. **Conversation Logs**: Optional with clear toggle, inform user about privacy implications
6. **Local Processing**: All voice processing happens locally (Whisper runs offline)

---

## **8. Installation & Setup**

### **Requirements**
```
Python 3.10+
pip install customtkinter pystray pynput mcp anthropic google-generativeai requests
pip install faster-whisper sounddevice mss Pillow
pip install win10toast-click  # For Windows notifications (optional)
```

### **First Run**
1. Launch app → appears in system tray
2. Right-click tray icon → "Settings"
3. Configure at least one API key (Gemini/OpenRouter) or Ollama
4. Optionally configure MCP servers
5. Test with Ctrl+Shift+Space hotkey

---

## **9. Future Enhancements (Post-MVP)**

- Voice output (TTS response reading)
- Conversation history browser with search
- Export conversations to markdown
- Custom MCP server creator wizard
- Plugin system for custom integrations
- Multi-language support for UI
- Advanced prompt templates with variables
- Agent memory/context persistence across sessions
- Mobile companion app (view logs, send commands)

---

## **10. Testing Strategy**

- **Unit Tests**: Core agent logic, API managers, MCP client
- **Integration Tests**: MCP tool execution, confirmation flow
- **UI Tests**: Manual testing of all windows and interactions
- **Performance Tests**: Response times, Whisper transcription speed
- **Security Tests**: Command injection attempts, API key exposure checks

---

## **Summary**

This plan provides a complete roadmap for building a sophisticated local AI agent with:
- ✅ Modern UI with CustomTkinter
- ✅ Global hotkey access
- ✅ Voice input via local Whisper
- ✅ Screen context awareness
- ✅ MCP integration for computer control
- ✅ Transparent thinking process
- ✅ Command approval system
- ✅ Multi-model support (Gemini, OpenRouter, Ollama)
- ✅ System tray minimization
- ✅ Comprehensive logging

