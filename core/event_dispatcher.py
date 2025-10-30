# file: core/event_dispatcher.py

import asyncio
from collections import defaultdict
from typing import Callable, Any, Dict, List, Coroutine, Optional
from utils.config_loader import ConfigLoader # Added import

class EventDispatcher:
    """
    A comprehensive event bus for decoupled component communication.
    Supports both synchronous and asynchronous (asyncio) event handlers
    and processes events using a priority queue.
    """
    
    def __init__(self, config_loader: ConfigLoader): # Changed constructor for DI
        # A dictionary mapping event_type (str) to a list of listeners (Callable)
        self._listeners: Dict[str, List[Callable[..., Any]]] = defaultdict(list)
        
        # Load event priorities from config
        system_config = config_loader.get_config("system_config.json")
        self._event_priorities: Dict[str, int] = system_config.get("event_priorities", {})
        self._default_priority: int = self._event_priorities.get("DEFAULT", 50)
        
        # The priority queue for events
        self._event_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._dispatcher_task: Optional[asyncio.Task] = None

    def _get_priority(self, event_type: str) -> int:
        """
        Gets the best-matching priority for an event type.
        e.g., "UI.CLICK" will check "UI.CLICK", then "UI", then "DEFAULT".
        """
        parts = event_type.split('.')
        for i in range(len(parts), 0, -1):
            check_key = ".".join(parts[:i])
            if check_key in self._event_priorities:
                return self._event_priorities[check_key]
        return self._default_priority

    def subscribe(self, event_type: str, listener: Callable[..., Any]):
        """
        Subscribes a listener function to a specific event type.
        
        Args:
            event_type (str): The event to listen for (e.g., "UI_EVENT.OPEN_CHAT").
            listener (Callable): The function to call when the event is published.
        """
        self._listeners[event_type].append(listener)

    def unsubscribe(self, event_type: str, listener: Callable[..., Any]):
        """Removes a specific listener from an event type."""
        if event_type in self._listeners:
            try:
                self._listeners[event_type].remove(listener)
            except ValueError:
                # Listener was not found, which is fine
                pass

    async def publish(self, event_type: str, *args, **kwargs):
        """
        Publishes an event by adding it to the priority queue.
        
        This method is now very fast and non-blocking. The actual
        listener execution happens in the background dispatcher loop.
        
        Args:
            event_type (str): The event being published.
            *args: Positional arguments to pass to the listeners.
            **kwargs: Keyword arguments to pass to the listeners.
        """
        priority = self._get_priority(event_type)
        # Item format: (priority, event_type, args, kwargs)
        event_item = (priority, event_type, args, kwargs)
        await self._event_queue.put(event_item)

    async def _execute_listeners(self, event_type: str, *args, **kwargs):
        """
        Executes all listeners for a given event.
        (This is the logic from the old 'publish' method).
        """
        if event_type not in self._listeners:
            return  # No one is listening, do nothing

        tasks_to_run = []
        for listener in self._listeners[event_type]:
            if asyncio.iscoroutinefunction(listener):
                # If the listener is an 'async def' function, create a task
                tasks_to_run.append(listener(*args, **kwargs))
            else:
                # If it's a regular 'def' function, just call it.
                try:
                    listener(*args, **kwargs)
                except Exception as e:
                    print(f"Error in synchronous listener for {event_type}: {e}")
                    # Optionally, publish an ERROR_EVENT here
        
        # Await all the 'async def' listeners concurrently
        if tasks_to_run:
            # Use return_exceptions=True so one failed listener doesn't
            # stop all other async listeners for this event.
            results = await asyncio.gather(*tasks_to_run, return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    print(f"Error in asynchronous listener for {event_type}: {res}")

    async def _dispatcher_loop(self):
        """
        The main worker loop that processes events from the queue.
        """
        try:
            while True:
                # Get the highest-priority event (lowest number)
                priority, event_type, args, kwargs = await self._event_queue.get()
                
                try:
                    # Execute all listeners for this event
                    await self._execute_listeners(event_type, *args, **kwargs)
                except Exception as e:
                    # Catch errors from _execute_listeners itself (e.g., gather)
                    print(f"Critical error during listener execution for {event_type}: {e}")
                finally:
                    # Ensure task_done is called even if listeners fail
                    self._event_queue.task_done()
                    
        except asyncio.CancelledError:
            print("Event dispatcher loop cancelled.")
        except Exception as e:
            print(f"Event dispatcher loop crashed: {e}")

    def start(self):
        """Starts the background event processing loop."""
        if self._dispatcher_task is None or self._dispatcher_task.done():
            self._dispatcher_task = asyncio.create_task(self._dispatcher_loop())
            print("Event dispatcher started.")

    async def stop(self):
        """Stops the background event processing loop."""
        if self._dispatcher_task and not self._dispatcher_task.done():
            self._dispatcher_task.cancel()
            await asyncio.wait([self._dispatcher_task], timeout=1.0) # Give it a moment to shut down
            self._dispatcher_task = None
            print("Event dispatcher stopped.")