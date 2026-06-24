from abc import ABC, abstractmethod
from typing import Callable, Type, Any
from gqos.messaging.contracts import Event, Command, MessageEnvelope

class IEventBus(ABC):
    """
    Interface for publishing events to N subscribers.
    """
    @abstractmethod
    def publish(self, envelope: MessageEnvelope[Event]) -> None:
        """Publishes an event to all registered subscribers."""
        pass

    @abstractmethod
    def subscribe(self, event_type: Type[Event], handler: Callable[[MessageEnvelope[Event]], None]) -> None:
        """Registers a handler for a specific Event type."""
        pass

    @abstractmethod
    def unsubscribe(self, event_type: Type[Event], handler: Callable[[MessageEnvelope[Event]], None]) -> None:
        """Removes a handler for a specific Event type."""
        pass


class ICommandBus(ABC):
    """
    Interface for dispatching commands to exactly 1 handler.
    """
    @abstractmethod
    def dispatch(self, envelope: MessageEnvelope[Command]) -> Any:
        """Dispatches a command to its registered handler and returns the result."""
        pass

    @abstractmethod
    def register_handler(self, command_type: Type[Command], handler: Callable[[MessageEnvelope[Command]], Any]) -> None:
        """Registers exactly one handler for a specific Command type."""
        pass
