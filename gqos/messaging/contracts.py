from dataclasses import dataclass, field
from typing import Any, Dict, Optional, TypeVar, Generic
import uuid
import time

@dataclass(frozen=True)
class MessagePayload:
    """Base class for all payloads."""
    pass

@dataclass(frozen=True)
class Event(MessagePayload):
    """Base class for all Events (Facts that happened)."""
    pass

@dataclass(frozen=True)
class Command(MessagePayload):
    """Base class for all Commands (Intents to change)."""
    pass

T = TypeVar('T', bound=MessagePayload)

@dataclass(frozen=True)
class MessageEnvelope(Generic[T]):
    """
    Standard envelope wrapping all messages to provide uniform metadata.
    """
    message_id: str
    payload: T
    version: int
    timestamp: float = field(default_factory=time.time)
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    run_id: Optional[str] = None
    sequence_number: int = 0

    @classmethod
    def create(cls, payload: T, version: int, correlation_id: Optional[str] = None, trace_id: Optional[str] = None, run_id: Optional[str] = None, sequence_number: int = 0) -> 'MessageEnvelope[T]':
        """Helper to create an envelope with a generated MessageID."""
        return cls(
            message_id=str(uuid.uuid4()),
            payload=payload,
            version=version,
            correlation_id=correlation_id,
            trace_id=trace_id,
            run_id=run_id,
            sequence_number=sequence_number
        )
