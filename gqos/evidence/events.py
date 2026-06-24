from dataclasses import dataclass
from gqos.messaging.contracts import Event
from gqos.domain.interfaces import IArtifact

@dataclass(frozen=True)
class ArtifactCreatedEvent(Event):
    artifact: IArtifact

@dataclass(frozen=True)
class ArtifactPromotedEvent(Event):
    promotion_record_id: str
    target_artifact_id: str

@dataclass(frozen=True)
class ValidationFailedEvent(Event):
    target_artifact_id: str
    reason: str
