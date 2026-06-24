from enum import Enum
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from gqos.common.enums import TradeDirection

class RoundingPolicy(Enum):
    ROUND_DOWN = 1
    ROUND_UP = 2
    BANKERS = 3
    LOT_SIZE = 4

@dataclass(frozen=True)
class StrategyMetrics:
    win_rate: Decimal
    win_loss_ratio: Decimal

@dataclass(frozen=True)
class VolatilityMetrics:
    atr: Decimal
    annualized_volatility: Optional[Decimal] = None

@dataclass(frozen=True)
class SizingRequest:
    strategy_id: str
    symbol: str
    direction: TradeDirection
    entry_price: Decimal
    stop_loss_price: Optional[Decimal] = None
    conviction: Optional[Decimal] = None
    metrics: Optional[StrategyMetrics] = None
    volatility: Optional[VolatilityMetrics] = None

@dataclass(frozen=True)
class SizingResult:
    quantity: Decimal
    estimated_value: Decimal
    risk_amount: Decimal
    capital_used: Decimal
    sizing_reason: str
    dynamic_stop_loss: Optional[Decimal] = None

class InvalidSizingRequestError(Exception):
    pass
