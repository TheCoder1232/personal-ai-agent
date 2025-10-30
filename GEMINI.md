# GEMINI.md

## Project Overview

This project is a personal AI assistant that runs on your local machine. It's built with Python and features a plugin-based architecture, allowing for easy extension of its capabilities. The UI is built with CustomTkinter, and it supports multiple LLM providers through LiteLLM. The application runs in the system tray and can be controlled via global hotkeys.

### Key Technologies

*   **Python**: The core programming language.
*   **CustomTkinter**: For the graphical user interface.
*   **LiteLLM**: To support various LLM providers like Gemini, Ollama, and OpenRouter.
*   **Plugin Architecture**: For extensibility.

## Building and Running

### 1. Setup

It is recommended to use a virtual environment.

```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# On Windows
.venv\Scripts\activate
# On macOS/Linux
source .venv/bin/activate
```

### 2. Install Dependencies

The project uses `uv` to manage dependencies, as indicated by the `uv.lock` file.

```bash
# Install dependencies using uv
uv pip install -r requirements.txt
```

If `requirements.txt` is not available, you can install the dependencies from `pyproject.toml`:

```bash
uv pip install -e .
```

### 3. Configure API Keys

The application uses environment variables for API keys.

**On Windows (Command Prompt):**

```bash
set GEMINI_API_KEY="your_google_ai_studio_key"
set OPENROUTER_API_KEY="your_openrouter_key"
```

**On macOS/Linux:**

```bash
export GEMINI_API_KEY="your_google_ai_studio_key"
export OPENROUTER_API_KEY="your_openrouter_key"
```

### 4. Run the Application

```bash
python main.py
```

The application will start and an icon will appear in the system tray.

## Development Conventions

*   **Service Locator Pattern**: The project uses a service locator for dependency injection, which helps in decoupling components. Core services are registered in `main.py` and can be accessed globally.
*   **Plugin-Based Architecture**: New features are added as plugins in the `plugins/` directory. Each plugin must inherit from a base class and implement the required methods.
*   **Event-Driven Architecture**: The application uses an event dispatcher to communicate between different components. This allows for loose coupling and better separation of concerns.
*   **Configuration**: All user-facing configurations are stored in JSON files in the `config/` directory.
*   **Logging**: The application uses the `logging` module for logging. The logging is configured in `utils/logger.py`.
