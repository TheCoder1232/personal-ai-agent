# file: core/plugin_manager.py

import importlib.util
import inspect
from pathlib import Path
from typing import List, Dict, Type
from core.service_locator import ServiceLocator
from plugins import PluginBase # Import the base class

class PluginManager:
    """
    Discovers, loads, and manages all plugins from the /plugins directory.
    
    It injects the service locator into each plugin upon instantiation,
    allowing plugins to access core services.
    """
    
    def __init__(self, service_locator: ServiceLocator):
        self.locator = service_locator
        self.plugins_dir = Path(__file__).parent.parent / "plugins"
        self.loaded_plugins: Dict[str, PluginBase] = {}
        self.event_dispatcher = self.locator.resolve("event_dispatcher")

    async def load_plugins(self):
        """
        Scans the plugins directory, imports modules, and initializes plugins.
        """
        print(f"Loading plugins from: {self.plugins_dir}")
        
        for file_path in self.plugins_dir.glob("*.py"):
            if file_path.name == "__init__.py":
                continue # Skip the base class file

            module_name = file_path.stem
            print(f"Found potential plugin: {module_name}")
            
            try:
                # Dynamically import the module
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if not spec or not spec.loader:
                    raise ImportError(f"Could not create spec for {module_name}")
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find all classes in the module that are subclasses of PluginBase
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, PluginBase) and obj is not PluginBase:
                        print(f"  -> Found plugin class: {name}")
                        
                        # 1. Instantiate the plugin, injecting the locator
                        plugin_instance: PluginBase = obj(self.locator)
                        
                        # 2. Call its initialize method
                        plugin_instance.initialize()
                        
                        # 3. Store it
                        metadata = plugin_instance.get_metadata()
                        plugin_id = metadata.get("name", module_name)
                        self.loaded_plugins[plugin_id] = plugin_instance
                        
                        print(f"  -> Successfully loaded and initialized '{plugin_id}'")
                        
                        # 4. (Optional) Publish an event
                        await self.event_dispatcher.publish(
                            "PLUGIN_EVENT.LOADED", 
                            plugin_id=plugin_id,
                            metadata=metadata
                        )
                        
            except Exception as e:
                print(f"Error loading plugin from {file_path.name}: {e}")
                # Optionally publish an ERROR_EVENT
                await self.event_dispatcher.publish(
                    "ERROR_EVENT.PLUGIN_CRASH", 
                    plugin_file=file_path.name,
                    error=str(e)
                )

    def get_plugin(self, name: str) -> PluginBase:
        """Gets a loaded plugin instance by name."""
        return self.loaded_plugins[name]

    def get_all_plugins(self) -> List[PluginBase]:
        """Returns a list of all loaded plugin instances."""
        return list(self.loaded_plugins.values())