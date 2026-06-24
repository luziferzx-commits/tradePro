from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from gqos.messaging.contracts import Event
from gqos.common.enums import TradeDirection

@dataclass(frozen=True)
class PositionOpenedEvent(Event):
    strategy_id: str
    symbol: str
    direction: TradeDirection
    quantity: Decimal
    average_price: Decimal

@dataclass(frozen=True)
class PositionAdjustedEvent(Event):
    strategy_id: str
    symbol: str
    direction: TradeDirection
    new_quantity: Decimal
    new_average_price: Decimal
    quantity_changed: Decimal

@dataclass(frozen=True)
class PositionClosedEvent(Event):
    strategy_id: str
    symbol: str
    direction: TradeDirection
    quantity_closed: Decimal
    exit_price: Decimal

@dataclass(frozen=True)
class RealizedPnLEmittedEvent(Event):
    strategy_id: str
    symbol: str
    realized_pnl: Decimal

@dataclass(frozen=True)
class FeeChargedEvent(Event):
    strategy_id: str
    amount: Decimal
    currency: str
    reason: str
