from enum import Enum
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from gqos.messaging.contracts import Event
from gqos.common.enums import TradeDirection

class OrderStatus(Enum):
    NEW = "NEW"
    ACK = "ACK"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

@dataclass(frozen=True)
class OrderUpdateEvent(Event):
    """
    Emitted by the OMS when an order changes state.
    """
    order_id: str
    symbol: str
    status: OrderStatus
    filled_quantity: Decimal
    remaining_quantity: Decimal
    average_fill_price: Decimal
    message: str = ""

@dataclass(frozen=True)
class ReconciliationFillEvent(Event):
    """
    Emitted during startup if the Local Ledger is out of sync with Broker Truth.
    """
    symbol: str
    direction: TradeDirection
    quantity: Decimal
    execution_price: Decimal
    reason: str

@dataclass(frozen=True)
class HeartbeatEvent(Event):
    """
    Emitted by the Broker Adapter to signal connection health.
    """
    timestamp: float
    latency_ms: float
    status: str

@dataclass(frozen=True)
class OrderAdjustedEvent(Event):
    """
    Emitted by the Broker Adapter when an order is adjusted (e.g., lot size/tick size rounding)
    before being sent to the exchange.
    """
    order_id: str
    symbol: str
    original_quantity: Decimal
    adjusted_quantity: Decimal
    original_price: Decimal
    adjusted_price: Decimal
    reason: str
