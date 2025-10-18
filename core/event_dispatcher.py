# file: core/event_dispatcher.py

import asyncio
from collections import defaultdict
from typing import Callable, Any, Dict, List, Coroutine

class EventDispatcher:
    """
    A comprehensive event bus for decoupled component communication.
    Supports both synchronous and asynchronous (asyncio) event handlers.
    """
    
    def __init__(self):
        # A dictionary mapping event_type (str) to a list of listeners (Callable)
        self._listeners: Dict[str, List[Callable[..., Any]]] = defaultdict(list)

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
        Publishes an event, calling all subscribed listeners.
        
        This method is asynchronous and will 'await' any listeners
        that are coroutines (defined with 'async def').
        
        Args:
            event_type (str): The event being published.
            *args: Positional arguments to pass to the listeners.
            **kwargs: Keyword arguments to pass to the listeners.
        """
        if event_type not in self._listeners:
            return # No one is listening, do nothing

        # Create a list of tasks to run.
        # This includes normal functions and coroutines.
        tasks_to_run = []
        
        for listener in self._listeners[event_type]:
            if asyncio.iscoroutinefunction(listener):
                # If the listener is an 'async def' function, create a task
                tasks_to_run.append(listener(*args, **kwargs))
            else:
                # If it's a regular 'def' function, just call it.
                # We wrap it in a small async helper to run it in the loop
                # This is a simple way to not block, but for true sync-to-async,
                # you might use loop.run_in_executor in a real-world scenario.
                # For this project, calling it directly is fine if it's fast.
                try:
                    listener(*args, **kwargs)
                except Exception as e:
                    print(f"Error in synchronous listener for {event_type}: {e}")
                    # Optionally, publish an ERROR_EVENT here
                    
        # Await all the 'async def' listeners concurrently
        if tasks_to_run:
            await asyncio.gather(*tasks_to_run)