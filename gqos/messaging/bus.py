import threading
import queue
from typing import Callable, Type, Dict, List, Any
from gqos.messaging.interfaces import IEventBus, ICommandBus
from gqos.messaging.contracts import Event, Command, MessageEnvelope
from gqos.kernel.interfaces import ILogger

class LocalEventBus(IEventBus):
    """
    In-memory synchronous Event Bus with FIFO dispatch and exception isolation.
    """
    def __init__(self, logger: ILogger, event_store=None):
        self._logger = logger
        self._event_store = event_store
        self._subscribers: Dict[Type[Event], List[Callable[[MessageEnvelope[Event]], None]]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: Type[Event], handler: Callable[[MessageEnvelope[Event]], None]) -> None:
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: Type[Event], handler: Callable[[MessageEnvelope[Event]], None]) -> None:
        with self._lock:
            if event_type in self._subscribers and handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)

    def publish(self, envelope: MessageEnvelope[Event]) -> None:
        """
        Dispatches synchronously to all handlers.
        Follows Subscriber Exception Policy: Exceptions are caught, logged, and skipped.
        """
        payload_type = type(envelope.payload)
        
        if self._event_store:
            envelope = self._event_store.append(envelope)
            
        with self._lock:
            handlers = self._subscribers.get(payload_type, []).copy()
            
        for handler in handlers:
            try:
                handler(envelope)
            except Exception as e:
                # ADR-0003: Log and continue
                self._logger.log("ERROR", f"Subscriber {handler.__name__} failed on Event {payload_type.__name__}: {str(e)}")


class LocalCommandBus(ICommandBus):
    """
    In-memory synchronous Command Bus enforcing Exactly-One handler.
    """
    def __init__(self, logger: ILogger, event_store=None):
        self._logger = logger
        self._event_store = event_store
        self._handlers: Dict[Type[Command], Callable[[MessageEnvelope[Command]], Any]] = {}
        self._lock = threading.Lock()

    def register_handler(self, command_type: Type[Command], handler: Callable[[MessageEnvelope[Command]], Any]) -> None:
        with self._lock:
            if command_type in self._handlers:
                raise ValueError(f"Command {command_type.__name__} already has a registered handler. Exactly-One allowed.")
            self._handlers[command_type] = handler

    def dispatch(self, envelope: MessageEnvelope[Command]) -> Any:
        """
        Dispatches synchronously to the single registered handler.
        Exceptions propagate naturally.
        """
        payload_type = type(envelope.payload)
        
        if self._event_store:
            envelope = self._event_store.append(envelope)
            
        with self._lock:
            handler = self._handlers.get(payload_type)
            
        if not handler:
            raise ValueError(f"No handler registered for Command {payload_type.__name__}.")
            
        return handler(envelope)
