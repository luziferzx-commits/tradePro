from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from gqos.messaging.contracts import Command, Event
from gqos.common.enums import TradeDirection

@dataclass(frozen=True)
class ExecuteTradeCommand(Command):
    """
    A command that requests the execution of a trade.
    Intercepted by Risk Budget Engine before reaching the broker plugin.
    """
    symbol: str
    direction: TradeDirection
    quantity: Decimal
    estimated_value: Decimal
    strategy_id: str

@dataclass(frozen=True)
class RiskBudgetAllocated(Event):
    budget_id: str
    allocation_id: str
    strategy_id: str
    allocated_amount: Decimal
    new_utilized_capacity: Decimal
    total_capacity: Decimal

@dataclass(frozen=True)
class RiskBudgetExhausted(Event):
    budget_id: str
    strategy_id: str
    requested_amount: Decimal
    current_utilized: Decimal
    total_capacity: Decimal
    reason: str

@dataclass(frozen=True)
class RiskBudgetReleased(Event):
    budget_id: str
    allocation_id: str
    strategy_id: str
    released_amount: Decimal
    new_utilized_capacity: Decimal

@dataclass(frozen=True)
class TradeRejectedByRiskEvent(Event):
    strategy_id: str
    symbol: str
    requested_value: Decimal
    reason: str

@dataclass(frozen=True)
class RiskBudgetNearLimit(Event):
    budget_id: str
    strategy_id: str
    utilized_percentage: Decimal

@dataclass(frozen=True)
class TripCircuitBreakerCommand(Command):
    breaker_id: str
    reason: str

@dataclass(frozen=True)
class ResetCircuitBreakerCommand(Command):
    breaker_id: str

@dataclass(frozen=True)
class TestCircuitBreakerCommand(Command):
    breaker_id: str

@dataclass(frozen=True)
class CircuitBreakerTripped(Event):
    breaker_id: str
    reason: str

@dataclass(frozen=True)
class CircuitBreakerReset(Event):
    breaker_id: str

@dataclass(frozen=True)
class CircuitBreakerHalfOpened(Event):
    breaker_id: str

@dataclass(frozen=True)
class TradeRejectedByCircuitBreaker(Event):
    strategy_id: str
    symbol: str
    requested_value: Decimal
    reason: str

@dataclass(frozen=True)
class TradeExecutedEvent(Event):
    strategy_id: str
    symbol: str
    direction: TradeDirection
    quantity: Decimal
    execution_price: Decimal
    intended_price: Optional[Decimal] = None
    slippage_amount: Optional[Decimal] = None
@dataclass(frozen=True)
class TradeRejectedByExposureLimit(Event):
    strategy_id: str
    symbol: str
    requested_value: Decimal
    limit_type: str
    reason: str
