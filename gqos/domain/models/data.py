from dataclasses import dataclass, field
from typing import List, Dict, Any
from gqos.domain.interfaces import IArtifact
from gqos.domain.value_objects import Symbol, Timeframe
from gqos.domain.utils import generate_deterministic_hash

@dataclass(frozen=True)
class Feature(IArtifact):
    name: str
    value: float
    timestamp: float
    _parent_ids: List[str] = field(default_factory=list)

    @property
    def artifact_id(self) -> str:
        return generate_deterministic_hash(self)
        
    @property
    def parent_ids(self) -> List[str]:
        return self._parent_ids

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Feature):
            return False
        return self.artifact_id == other.artifact_id

@dataclass(frozen=True)
class Dataset(IArtifact):
    symbol: Symbol
    timeframe: Timeframe
    features: List[Feature]
    _parent_ids: List[str] = field(default_factory=list)

    @property
    def artifact_id(self) -> str:
        return generate_deterministic_hash(self)
        
    @property
    def parent_ids(self) -> List[str]:
        # Parents are explicitly passed parent_ids + implicitly the features it contains
        return self._parent_ids + [f.artifact_id for f in self.features]

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Dataset):
            return False
        return self.artifact_id == other.artifact_id
