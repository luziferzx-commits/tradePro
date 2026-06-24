from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from gqos.messaging.contracts import Command, Event
from gqos.common.enums import TradeDirection
from gqos.sizing.models import SizingRequest, SizingResult, StrategyMetrics, VolatilityMetrics
from gqos.sizing.policies import ISizingPolicy

@dataclass(frozen=True)
class SizePositionCommand(Command):
    """
    A command dispatched by a strategy indicating an intent to trade.
    Intercepted by SizingPipeline to calculate the exact position size.
    """
    strategy_id: str
    symbol: str
    direction: TradeDirection
    entry_price: Decimal
    stop_loss_price: Optional[Decimal] = None
    conviction: Optional[Decimal] = None
    metrics: Optional[StrategyMetrics] = None
    volatility: Optional[VolatilityMetrics] = None

@dataclass(frozen=True)
class PositionSizedEvent(Event):
    """
    An event emitted after the PositionSizingEngine calculates the size.
    Contains the sizing reason and exact metrics for evidence.
    """
    strategy_id: str
    symbol: str
    direction: TradeDirection
    result: SizingResult
    policy_name: str
    policy_version: str
    policy_parameters_hash: str
    dynamic_stop_loss: Optional[Decimal] = None

@dataclass(frozen=True)
class SizingFailedEvent(Event):
    """
    An event emitted when position sizing fails due to invalid inputs
    or negative/zero calculation results.
    """
    strategy_id: str
    symbol: str
    direction: TradeDirection
    reason: str
