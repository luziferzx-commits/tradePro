import time
from dataclasses import dataclass, field
from decimal import Decimal

@dataclass(frozen=True)
class RiskBudget:
    """Immutable definition of a Risk Budget."""
    budget_id: str
    total_capacity: Decimal
    utilized_capacity: Decimal
    emitted_thresholds: frozenset[Decimal] = field(default_factory=frozenset)

@dataclass(frozen=True)
class AllocationRequest:
    """A request to consume risk budget."""
    allocation_id: str
    budget_id: str
    strategy_id: str
    requested_amount: Decimal
    timestamp: float = field(default_factory=time.time)

@dataclass(frozen=True)
class AllocationResult:
    """Result of an allocation request."""
    success: bool
    amount_allocated: Decimal
    budget_id: str
    allocation_id: str
    new_utilized_capacity: Decimal
    total_capacity: Decimal
    reason: str = ""

@dataclass(frozen=True)
class RiskBudgetSnapshot:
    """A point-in-time snapshot of a budget for auditing."""
    budget_id: str
    total_capacity: Decimal
    utilized_capacity: Decimal
    timestamp: float = field(default_factory=time.time)
