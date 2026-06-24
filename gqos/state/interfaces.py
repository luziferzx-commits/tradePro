from abc import ABC, abstractmethod
from typing import Any, Dict
from gqos.state.models import StateSnapshot

class IStateStore(ABC):
    """
    Interface for State Management.
    """
    @abstractmethod
    def get_snapshot(self) -> StateSnapshot:
        """Returns the current immutable snapshot of the entire state."""
        pass

    @abstractmethod
    def apply(self, changes: Dict[str, Any], metadata: Dict[str, Any]) -> StateSnapshot:
        """
        Applies a set of changes and returns the newly generated snapshot.
        Mutations are merged into the existing state tree.
        """
        pass

    @abstractmethod
    def restore(self, snapshot: StateSnapshot) -> None:
        """Restores the system state entirely to a specific past snapshot."""
        pass
