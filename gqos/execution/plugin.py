from abc import ABC, abstractmethod
from typing import List, Type
from gqos.messaging.contracts import Command, MessageEnvelope

class IPlugin(ABC):
    @abstractmethod
    def supported_commands(self) -> List[Type[Command]]:
        """Returns a list of Command types this plugin handles."""
        pass
        
    @abstractmethod
    def handle(self, envelope: MessageEnvelope[Command], bus) -> None:
        """
        Handles the command and publishes resulting Events to the bus.
        Must not interact with the ArtifactRegistry directly.
        """
        pass
