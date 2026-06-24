from dataclasses import dataclass
from typing import List, Any
from gqos.domain.interfaces import IArtifact
from gqos.domain.models.execution import Position
from gqos.domain.utils import generate_deterministic_hash

@dataclass(frozen=True)
class RiskMetrics(IArtifact):
    position: Position
    drawdown_percent: float
    exposure_usd: float
    timestamp: float

    def __post_init__(self):
        if self.drawdown_percent < 0:
            raise ValueError(f"Drawdown cannot be negative, got {self.drawdown_percent}")
        if self.exposure_usd < 0:
            raise ValueError(f"Exposure cannot be negative, got {self.exposure_usd}")

    @property
    def artifact_id(self) -> str:
        return generate_deterministic_hash(self)
        
    @property
    def parent_ids(self) -> List[str]:
        return [self.position.artifact_id]

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, RiskMetrics):
            return False
        return self.artifact_id == other.artifact_id
