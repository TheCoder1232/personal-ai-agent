# GEMINI.md: Project Context for the Personal AI Agent

This document provides a comprehensive overview of the "Personal AI Agent" project, intended to be used as a foundational context for an AI assistant.

## Project Overview

This is a Python-based personal AI assistant designed to run as a local desktop application. It features a plugin-based architecture, allowing for dynamic extension of its capabilities. The user interacts with the agent through a modern graphical user interface (GUI) built with CustomTkinter, which includes a system tray icon for easy access and a popup window for conversations.

The core of the application is event-driven and modular, using a service locator pattern for dependency injection and an event dispatcher for decoupled communication between components. This design promotes maintainability and extensibility.

Key technologies and libraries include:
- **UI**: `customtkinter` for the main windows, `pystray` for the system tray icon, and `PIL` for image handling.
- **AI/LLM**: `litellm` is used as a compatibility layer to seamlessly connect with various Large Language Model (LLM) providers like Google Gemini, OpenRouter, and others.
- **Core Logic**: A custom event-driven framework with a service locator for managing dependencies.
- **Plugins**: The application can be extended with plugins located in the `plugins/` directory. An example is the `screen_capture.py` plugin, which uses `mss` to take screenshots.
- **Input**: `pynput` is used for managing global hotkeys.
- **Packaging & Dependencies**: The project uses `pyproject.toml` to define dependencies, which can be managed by tools like `pip` or `uv`.
- **Testing**: `pytest` and `pytest-asyncio` are used for unit and integration testing.

## Building and Running

### 1. Setup and Installation

The project uses `uv` for environment and dependency management, as indicated by the `uv.lock` file and `pyproject.toml`.

**Install dependencies:**
```bash
# Install main dependencies
uv pip install -e .

# Install development dependencies (including pytest)
uv pip install -e ".[dev]"
```

### 2. Running the Application

The main entry point is `main.py`.

**To run the application:**
```bash
python main.py
```
or using `uv`:
```bash
uv run main.py
```
The application will start in the background with an icon in the system tray.

### 3. Running Tests

Tests are located in the `tests/` directory and are run using `pytest`.

**To run the test suite:**
```bash
pytest
```

## Development Conventions

- **Architecture**: The project is structured into distinct modules:
    - `core/`: Core services like the `Agent`, `ApiManager`, `EventDispatcher`, and `ServiceLocator`.
    - `ui/`: UI components, including `TrayManager` and `PopupWindow`.
    - `plugins/`: Self-contained feature extensions.
    - `utils/`: Utility classes like `ConfigLoader` and `logger`.
    - `config/`: All user-facing JSON configuration files.
    - `input/`: Global hotkey management.
    - `tests/`: Automated tests.

- **Dependency Management**: A `ServiceLocator` (`core/service_locator.py`) is used for dependency injection, promoting loose coupling between components. Services are registered in `main.py` and resolved where needed.

- **Event-Driven Communication**: An `EventDispatcher` (`core/event_dispatcher.py`) facilitates communication between different parts of the application. Components can publish events and subscribe to events from other components without direct dependencies.

- **Configuration**: Configuration is loaded from JSON files in the `config/` directory by the `ConfigLoader` utility. This allows for easy modification of settings without changing the code.

- **Code Style**: The code adheres to standard Python conventions (PEP 8) and utilizes type hints for improved readability and static analysis.

- **Plugin Development**: New features should be implemented as plugins. A new plugin requires creating a class that inherits from `PluginBase` and implementing the required methods. The `screen_capture.py` plugin serves as a good example.
