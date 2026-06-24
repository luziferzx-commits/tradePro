from enum import Enum
from dataclasses import dataclass, field
from decimal import Decimal
import time

class CircuitState(Enum):
    CLOSED = 1     # Normal operations
    OPEN = 2       # Breaker tripped, trading halted
    HALF_OPEN = 3  # Testing recovery

@dataclass(frozen=True)
class CircuitBreaker:
    breaker_id: str
    state: CircuitState = CircuitState.CLOSED
    tripped_reason: str = ""
    tripped_at: float = 0.0
    version: int = 1

@dataclass(frozen=True)
class CircuitBreakerSnapshot:
    breaker_id: str
    state: CircuitState
    version: int
    parent_version: int
    timestamp: float = field(default_factory=time.time)

@dataclass(frozen=True)
class DailyLossLimit:
    breaker_id: str
    max_daily_loss: Decimal
    current_daily_loss: Decimal
