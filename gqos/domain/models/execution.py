from dataclasses import dataclass
from typing import List, Any
from gqos.domain.interfaces import IArtifact
from gqos.domain.value_objects import Price, LotSize, Symbol
from gqos.domain.models.intelligence import Decision
from gqos.domain.utils import generate_deterministic_hash

@dataclass(frozen=True)
class Trade(IArtifact):
    symbol: Symbol
    entry_price: Price
    lot_size: LotSize
    decision: Decision # Composition
    timestamp: float

    @property
    def artifact_id(self) -> str:
        return generate_deterministic_hash(self)
        
    @property
    def parent_ids(self) -> List[str]:
        return [self.decision.artifact_id]

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Trade):
            return False
        return self.artifact_id == other.artifact_id

@dataclass(frozen=True)
class Position(IArtifact):
    symbol: Symbol
    current_size: LotSize
    average_entry: Price
    trades: List[Trade] # A position is made of trades
    
    @property
    def artifact_id(self) -> str:
        return generate_deterministic_hash(self)
        
    @property
    def parent_ids(self) -> List[str]:
        return [t.artifact_id for t in self.trades]

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Position):
            return False
        return self.artifact_id == other.artifact_id
