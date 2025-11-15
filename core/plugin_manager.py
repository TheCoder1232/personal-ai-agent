# file: core/plugin_manager.py

import importlib.util
import inspect
import logging
from pathlib import Path
from typing import List, Dict, Type, Tuple
from core.service_locator import ServiceLocator
from plugins import PluginBase
# --- ADDED: Custom Exception Imports ---
from core.exceptions import PluginLoadError
# --- ADDED: MemoryManager Import ---
from core.memory_manager import MemoryManager

class PluginManager:
    def __init__(self, service_locator: ServiceLocator):
        self.locator = service_locator
        self.plugins_dir = Path(__file__).parent.parent / "plugins"
        
        # --- MODIFIED: Renamed for clarity ---
        self._loaded_plugins: Dict[str, PluginBase] = {}
        
        # --- NEW: Stores metadata for lazy loading ---
        # Maps: plugin_id -> (file_path, class_name)
        self._plugin_registry: Dict[str, Tuple[Path, str]] = {}
        
        # --- MODIFIED: Resolve MemoryManager ---
        self.event_dispatcher = self.locator.resolve("event_dispatcher")
        self.logger = logging.getLogger(self.__class__.__name__)
        # Resolve memory manager, but it might not be registered in tests
        try:
            self.memory_manager: MemoryManager = self.locator.resolve("memory_manager")
        except KeyError:
            self.logger.warning("MemoryManager not registered. Plugin memory tracking will be disabled.")
            self.memory_manager = None # type: ignore
        # --- END MODIFIED SECTION ---
            
        # --- NEW: Load config to check lazy_load setting ---
        try:
            config_loader = self.locator.resolve("config_loader")
            self.lazy_load_enabled = config_loader.get("system_config.json", "lazy_load_plugins", True)
        except Exception as e:
            self.logger.warning(f"Could not read config. Defaulting to lazy_load_plugins=True. Error: {e}")
            self.lazy_load_enabled = True
            
        # --- NEW: Discover plugins on init, but don't load ---
        self._discover_plugins_sync()


    def _discover_plugins_sync(self):
        """
        Synchronously discovers plugins by scanning files and reading metadata.
        This does NOT initialize the plugins.
        """
        self.logger.info(f"Discovering plugins from: {self.plugins_dir}")
        
        for file_path in self.plugins_dir.glob("*.py"):
            if file_path.name == "__init__.py":
                continue

            module_name = file_path.stem
            
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if not spec or not spec.loader:
                    raise ImportError(f"Could not create spec for {module_name}")
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, PluginBase) and obj is not PluginBase:
                        self.logger.debug(f"  -> Found plugin class: {name}")
                        
                        try:
                            # --- CRITICAL: We must instantiate to get metadata ---
                            # But we DO NOT call initialize() here.
                            plugin_instance: PluginBase = obj(self.locator)
                            metadata = plugin_instance.get_metadata()
                            plugin_id = metadata.get("name", module_name)
                            
                            # Store how to load it later
                            self._plugin_registry[plugin_id] = (file_path, name, metadata) # (file_path, class_name, metadata)
                            self.logger.info(f"  -> Discovered and registered plugin id: '{plugin_id}' (module: {module_name}, class: {name})")
                            
                        except Exception as e:
                            self.logger.error(f"  -> FAILED to discover metadata for {name} from {file_path.name}: {e}", exc_info=True)
            
            except Exception as e:
                self.logger.error(f"Error discovering module from {file_path.name}: {e}", exc_info=True)

        # New: show all discovered plugin ids clearly
        self.logger.info(f"Discovered plugins (by id): {list(self._plugin_registry.keys())}")


    async def discover_and_load_plugins(self):
        """
        Handles the main plugin loading strategy based on config.
        """
        if self.lazy_load_enabled:
            self.logger.info(f"Lazy loading enabled. {len(self._plugin_registry)} plugins discovered.")
            self.logger.info("Checking for plugins that require eager loading...")
            eager_load_plugins = []
            for plugin_id, (_, _, metadata) in self._plugin_registry.items():
                if metadata.get("eager_load"):
                    eager_load_plugins.append(plugin_id)
            
            if eager_load_plugins:
                self.logger.info(f"Eager loading {len(eager_load_plugins)} plugins: {eager_load_plugins}")
                for plugin_id in eager_load_plugins:
                    try:
                        await self.get_plugin(plugin_id)
                    except PluginLoadError as e:
                        self.logger.error(f"Failed to eager-load plugin '{plugin_id}': {e}", exc_info=False)
                    except Exception as e:
                        self.logger.error(f"Unexpected error eager-loading plugin '{plugin_id}': {e}", exc_info=True)
        else:
            # Eager loading: load all discovered plugins now
            self.logger.info(f"Eager loading {len(self._plugin_registry)} discovered plugins: {list(self._plugin_registry.keys())}")
            for plugin_id in self._plugin_registry.keys():
                try:
                    self.logger.info(f"About to load plugin: '{plugin_id}'...")
                    await self.get_plugin(plugin_id) # This will force-load it
                # --- MODIFIED: Catch our custom error ---
                except PluginLoadError as e:
                    # Log the error, but continue loading other plugins (Plugin Isolation)
                    self.logger.error(f"Failed to eager-load plugin '{plugin_id}': {e}", exc_info=False) # Already logged
                except Exception as e:
                    self.logger.error(f"Unexpected error eager-loading plugin '{plugin_id}': {e}", exc_info=True)
            # After loading, log all loaded plugin ids
            self.logger.info(f"Loaded plugins: {list(self._loaded_plugins.keys())}")


    async def _load_plugin(self, name: str) -> PluginBase:
        """
        Internal async method to load, initialize, and register a single plugin.
        """
        if name not in self._plugin_registry:
            # --- MODIFIED: Raise custom exception ---
            raise PluginLoadError(f"Plugin '{name}' not found in registry. It was not discovered.")

        file_path, class_name, _ = self._plugin_registry[name]
        self.logger.debug(f"Loading '{name}' from {file_path.name} (class: {class_name})")
        
        try:
            # Re-import the module
            spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
            if not spec or not spec.loader:
                raise ImportError(f"Could not create spec for {file_path.stem}")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Get the specific class
            plugin_class: Type[PluginBase] = getattr(module, class_name)
            if not plugin_class:
                raise ImportError(f"Could not find class {class_name} in {file_path.name}")
            
            # --- This is the part from the old load_plugins ---
            plugin_instance: PluginBase = plugin_class(self.locator)
            plugin_instance.initialize() # <--- This is where a plugin can fail
            
            metadata = plugin_instance.get_metadata()
            
            self.logger.info(f"  -> Successfully loaded and initialized '{name}'")
            
            # --- ADDED: Track with MemoryManager ---
            if self.memory_manager:
                self.memory_manager.track_component(f"plugin:{name}")
                self.logger.debug(f"Registered plugin '{name}' with MemoryManager.")
            # --- END ADDED SECTION ---
            
            await self.event_dispatcher.publish(
                "PLUGIN_EVENT.LOADED", 
                plugin_id=name,
                metadata=metadata
            )
            return plugin_instance

        # --- START: MODIFIED SECTION ---
        # Catch specific code-level errors
        except (ImportError, AttributeError, TypeError) as e:
            self.logger.error(f"  -> FAILED (Code Error) to load plugin {name} from {file_path.name}: {e}", exc_info=True)
            await self.event_dispatcher.publish(
                "ERROR_EVENT.PLUGIN_CRASH", 
                plugin_name=name,
                error=str(e)
            )
            # Wrap in our custom exception
            raise PluginLoadError(f"Code error loading {name}: {e}") from e
        # Catch errors from the plugin's own initialize() method
        except Exception as e:
            self.logger.error(f"  -> FAILED (Init Error) to load plugin {name} from {file_path.name}: {e}", exc_info=True)
            await self.event_dispatcher.publish(
                "ERROR_EVENT.PLUGIN_CRASH", 
                plugin_name=name,
                error=str(e)
            )
            # Wrap in our custom exception
            raise PluginLoadError(f"Plugin '{name}' failed during initialize(): {e}") from e
        # --- END: MODIFIED SECTION ---

    
    async def get_plugin(self, name: str) -> PluginBase:
        """
        Gets a plugin by name.
        If lazy loading is enabled, this will load the plugin on first call.
        NOTE: This method is now ASYNCHRONOUS.
        """
        # 1. Check if already loaded
        if name in self._loaded_plugins:
            return self._loaded_plugins[name]
        
        # 2. Check if it exists but isn't loaded
        if name not in self._plugin_registry:
            # --- MODIFIED: Raise custom exception ---
            raise PluginLoadError(f"Plugin '{name}' is not discovered.")

        # 3. Load it (if lazy loading)
        if not self.lazy_load_enabled:
            # This shouldn't happen if eager-loading was successful
            self.logger.warning(f"Plugin '{name}' was not eager-loaded. Attempting to load now.")
        
        self.logger.info(f"Lazy loading plugin: {name}...")
        try:
            plugin_instance = await self._load_plugin(name)
            self._loaded_plugins[name] = plugin_instance
            return plugin_instance
        # --- MODIFIED: Catch our custom exception ---
        except PluginLoadError as e:
            self.logger.error(f"Failed to lazy-load plugin '{name}': {e}", exc_info=False) # Already logged
            raise e # Re-raise
        except Exception as e:
            self.logger.error(f"Unexpected error lazy-loading plugin '{name}': {e}", exc_info=True)
            # Wrap in our custom exception
            raise PluginLoadError(f"Unexpected error loading {name}: {e}") from e

    def get_all_plugins(self) -> List[PluginBase]:
        """Returns a list of *already loaded* plugins."""
        return list(self._loaded_plugins.values())