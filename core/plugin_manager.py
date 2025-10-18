# file: core/plugin_manager.py

import importlib.util
import inspect
import logging # <-- NEW
from pathlib import Path
from typing import List, Dict, Type
from core.service_locator import ServiceLocator
from plugins import PluginBase

class PluginManager:
    def __init__(self, service_locator: ServiceLocator):
        self.locator = service_locator
        self.plugins_dir = Path(__file__).parent.parent / "plugins"
        self.loaded_plugins: Dict[str, PluginBase] = {}
        self.event_dispatcher = self.locator.resolve("event_dispatcher")
        self.logger = logging.getLogger(self.__class__.__name__) # <-- NEW

    async def load_plugins(self):
        self.logger.info(f"Loading plugins from: {self.plugins_dir}") # <-- MODIFIED
        
        for file_path in self.plugins_dir.glob("*.py"):
            if file_path.name == "__init__.py":
                continue

            module_name = file_path.stem
            self.logger.debug(f"Found potential plugin: {module_name}") # <-- MODIFIED
            
            try:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if not spec or not spec.loader:
                    raise ImportError(f"Could not create spec for {module_name}")
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, PluginBase) and obj is not PluginBase:
                        self.logger.debug(f"  -> Found plugin class: {name}") # <-- MODIFIED
                        
                        try: # --- NEW: Safety wrapper for individual plugin ---
                            plugin_instance: PluginBase = obj(self.locator)
                            plugin_instance.initialize()
                            
                            metadata = plugin_instance.get_metadata()
                            plugin_id = metadata.get("name", module_name)
                            self.loaded_plugins[plugin_id] = plugin_instance
                            
                            self.logger.info(f"  -> Successfully loaded and initialized '{plugin_id}'") # <-- MODIFIED
                            
                            await self.event_dispatcher.publish(
                                "PLUGIN_EVENT.LOADED", 
                                plugin_id=plugin_id,
                                metadata=metadata
                            )
                        except Exception as e: # --- NEW ---
                            self.logger.error(f"  -> FAILED to load plugin {name} from {file_path.name}: {e}", exc_info=True)
                            await self.event_dispatcher.publish(
                                "ERROR_EVENT.PLUGIN_CRASH", 
                                plugin_name=name,
                                error=str(e)
                            )
                        # --- END NEW ---
                        
            except Exception as e:
                self.logger.error(f"Error loading module from {file_path.name}: {e}", exc_info=True) # <-- MODIFIED
                await self.event_dispatcher.publish(
                    "ERROR_EVENT.PLUGIN_CRASH", 
                    plugin_file=file_path.name,
                    error=str(e)
                )

    # ... (rest of file is unchanged)
    def get_plugin(self, name: str) -> PluginBase:
        return self.loaded_plugins[name]
    def get_all_plugins(self) -> List[PluginBase]:
        return list(self.loaded_plugins.values())