from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from gqos.messaging.contracts import Event
from gqos.sizing.portfolio import PortfolioSnapshot

@dataclass(frozen=True)
class CapitalAllocatedEvent(Event):
    strategy_id: str
    amount: Decimal
    new_buying_power: Decimal

@dataclass(frozen=True)
class CashReservedEvent(Event):
    strategy_id: str
    amount: Decimal
    allocation_id: str
    new_reserved_cash: Decimal
    new_buying_power: Decimal

@dataclass(frozen=True)
class CashReleasedEvent(Event):
    strategy_id: str
    amount: Decimal
    allocation_id: str
    new_reserved_cash: Decimal
    new_buying_power: Decimal
    reason: str

@dataclass(frozen=True)
class TradeRejectedByPortfolioEvent(Event):
    strategy_id: str
    symbol: str
    requested_amount: Decimal
    reason: str
