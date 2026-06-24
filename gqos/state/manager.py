import threading
from typing import Any, Dict
from gqos.state.interfaces import IStateStore
from gqos.state.models import StateSnapshot

class StateManager(IStateStore):
    """
    Thread-safe State Manager acting as the absolute authority on state mutation.
    Implements a Single-Writer lock paradigm.
    """
    def __init__(self, initial_metadata: Dict[str, Any] = None):
        self._write_lock = threading.Lock()
        
        # Internal mutable dictionary representing current state
        # Only StateManager is allowed to mutate this directly.
        self._current_data: Dict[str, Any] = {}
        
        self._current_version = 0
        
        if initial_metadata is None:
            initial_metadata = {"RunID": "default", "ReplayID": None}
            
        self._current_snapshot = StateSnapshot.create(
            version=self._current_version,
            data=self._current_data,
            metadata=initial_metadata
        )

    def get_snapshot(self) -> StateSnapshot:
        """
        Returns the most recently constructed snapshot.
        Because snapshots are immutable (MappingProxyType), this is completely thread-safe 
        and does not require acquiring a lock.
        """
        return self._current_snapshot

    def apply(self, changes: Dict[str, Any], metadata: Dict[str, Any] = None) -> StateSnapshot:
        """
        Acquires the exclusive write lock, applies changes, increments version, 
        and publishes a new immutable snapshot.
        """
        with self._write_lock:
            # Deep merge could be implemented here if nested dictionaries are expected
            # For now, top-level merge
            new_data = dict(self._current_data)
            new_data.update(changes)
            
            parent_version = self._current_version
            self._current_version += 1
            
            # Merge existing metadata with new metadata
            new_meta = dict(self._current_snapshot.metadata)
            if metadata:
                new_meta.update(metadata)
            
            new_snapshot = StateSnapshot.create(
                version=self._current_version,
                data=new_data,
                metadata=new_meta,
                parent_version=parent_version
            )
            
            self._current_data = new_data
            self._current_snapshot = new_snapshot
            
            return new_snapshot

    def restore(self, snapshot: StateSnapshot) -> None:
        """
        Force-overwrites the current state with a specific snapshot.
        Used primarily by the Replay engine.
        """
        with self._write_lock:
            # We copy out the frozen data back into mutable internal dictionary
            self._current_data = dict(snapshot.data)
            self._current_version = snapshot.version
            self._current_snapshot = snapshot
