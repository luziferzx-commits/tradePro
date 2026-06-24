from dataclasses import dataclass, field
from typing import List, Any
from gqos.domain.interfaces import IArtifact
from gqos.domain.value_objects import Probability
from gqos.domain.models.data import Dataset
from gqos.domain.utils import generate_deterministic_hash

@dataclass(frozen=True)
class Prediction(IArtifact):
    direction: int  # 1 for Long, -1 for Short, 0 for Neutral
    probability: Probability
    dataset: Dataset # Composition: Prediction based on a Dataset
    model_version: str

    @property
    def artifact_id(self) -> str:
        # Prevent circular references in hash by excluding dataset object itself, using its ID
        # Wait, generate_deterministic_hash handles nested dataclasses. Let's just hash everything.
        return generate_deterministic_hash(self)
        
    @property
    def parent_ids(self) -> List[str]:
        return [self.dataset.artifact_id]

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Prediction):
            return False
        return self.artifact_id == other.artifact_id

@dataclass(frozen=True)
class Decision(IArtifact):
    action: str  # e.g., "ENTER_LONG", "EXIT_SHORT", "HOLD"
    prediction: Prediction # Composition: Decision has a Prediction
    timestamp: float

    @property
    def artifact_id(self) -> str:
        return generate_deterministic_hash(self)
        
    @property
    def parent_ids(self) -> List[str]:
        return [self.prediction.artifact_id]

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Decision):
            return False
        return self.artifact_id == other.artifact_id
