from dataclasses import dataclass
from typing import Dict, Any, Optional
import pandas as pd

from gqos.messaging.contracts import Event

@dataclass(frozen=True)
class MarketDataEvent(Event):
    """
    A single live tick or an asynchronous bar payload.
    In M18, typically represents an OHLCV bar or a tick.
    """
    symbol: str
    price: float
    timestamp: float
    data: Optional[Dict[str, float]] = None

@dataclass(frozen=True)
class BarClosedEvent(Event):
    """
    Emitted when a bar is formally closed. This is the explicit trigger for Alpha Forecasts.
    """
    symbol: str
    timestamp: float
    bar_data: pd.Series

@dataclass(frozen=True)
class FeatureDriftEvent(Event):
    """
    Emitted when live data diverges from backtest feature boundaries (WARNING ONLY).
    """
    feature_id: str
    expected_mean: float
    actual_value: float
    z_score_deviation: float

@dataclass(frozen=True)
class DailyAttributionEvent(Event):
    """
    End of day PnL attribution separating Alpha edge from Friction.
    """
    date: str
    total_pnl: float
    alpha_pnl: float
    friction_cost: float
