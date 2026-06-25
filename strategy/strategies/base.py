from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import pandas as pd

@dataclass
class SignalDecision:
    strategy_id: str
    setup_name: str
    direction: str  # "BUY", "SELL", "NEUTRAL"
    confidence_score: float
    entry_reason: str
    stop_loss: float
    take_profit: float
    expected_rr: float
    invalidation_reason: str
    required_regime: str
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    
    # Risk-control amendments
    symbol: str = "UNKNOWN"
    timeframe: str = "UNKNOWN"
    timestamp: float = 0.0
    entry_price: float = 0.0
    risk_r: float = 1.0
    cost_estimate: float = 0.0
    edge_score: float = 0.0
    status: str = "NEUTRAL"  # "APPROVED", "REJECTED", "NEUTRAL"
    rejection_reason: str = ""

class BaseStrategy(ABC):
    """Base interface for all independent strategies (A, B, C, etc.)."""
    
    def __init__(self, symbol: str, timeframe: str):
        self.symbol = symbol
        self.timeframe = timeframe
        self.is_disabled_by_evidence = False
        self.disabled_reason = ""
        
    @abstractmethod
    def generate_signal(self, df: pd.DataFrame, regime: dict) -> SignalDecision:
        """
        Evaluate the latest data and return a complete SignalDecision.
        """
        pass
        
    def disable(self, reason: str):
        self.is_disabled_by_evidence = True
        self.disabled_reason = reason
        
    def get_neutral_signal(self, reason: str = "Neutral") -> SignalDecision:
        return SignalDecision(
            strategy_id=self.__class__.__name__,
            setup_name="None",
            direction="NEUTRAL",
            confidence_score=0.0,
            entry_reason=reason,
            stop_loss=0.0,
            take_profit=0.0,
            expected_rr=0.0,
            invalidation_reason=reason,
            required_regime="ANY",
            symbol=self.symbol,
            timeframe=self.timeframe,
            status="NEUTRAL",
            rejection_reason=reason
        )
