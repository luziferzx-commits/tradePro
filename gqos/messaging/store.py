import threading
import dataclasses
from typing import List, Dict, Optional
from abc import ABC, abstractmethod
from gqos.messaging.contracts import MessageEnvelope

class IEventStore(ABC):
    @abstractmethod
    def append(self, envelope: MessageEnvelope) -> MessageEnvelope:
        pass

    @abstractmethod
    def get_all(self) -> List[MessageEnvelope]:
        pass

    @abstractmethod
    def get_stream(self, correlation_id: str) -> List[MessageEnvelope]:
        pass

class InMemoryEventStore(IEventStore):
    """
    Append-only chronological ledger of all messages.
    """
    def __init__(self):
        self._store: List[MessageEnvelope] = []
        self._correlation_index: Dict[str, List[int]] = {}
        self._lock = threading.RLock()
        self._sequence: int = 1

    def append(self, envelope: MessageEnvelope) -> MessageEnvelope:
        with self._lock:
            # Inject monotonic sequence number if not set or overriding
            storing_envelope = dataclasses.replace(envelope, sequence_number=self._sequence)
            self._sequence += 1
            
            # We explicitly do NOT deduplicate. The EventStore is a literal chronological ledger.
            offset = len(self._store)
            self._store.append(storing_envelope)
            
            # Update O(1) correlation index
            if storing_envelope.correlation_id:
                if storing_envelope.correlation_id not in self._correlation_index:
                    self._correlation_index[storing_envelope.correlation_id] = []
                self._correlation_index[storing_envelope.correlation_id].append(offset)
                
            return storing_envelope

    def get_all(self) -> List[MessageEnvelope]:
        with self._lock:
            return list(self._store)

    def get_stream(self, correlation_id: str) -> List[MessageEnvelope]:
        with self._lock:
            offsets = self._correlation_index.get(correlation_id, [])
            return [self._store[offset] for offset in offsets]
