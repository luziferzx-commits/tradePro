from typing import List
from .base import BaseStrategy
from .strategy_a_breakout import StrategyABreakout
from .strategy_b_trend_pullback import StrategyBTrendPullback
from .strategy_c_mean_reversion import StrategyCMeanReversion

class StrategyRegistry:
    """
    Maintains and instantiates the active strategies for a given symbol and timeframe.
    """
    def __init__(self, symbol: str, timeframe: str):
        self.symbol = symbol
        self.timeframe = timeframe
        self._strategies = self._initialize_strategies()
        
    def _initialize_strategies(self) -> List[BaseStrategy]:
        strategies = [
            StrategyABreakout(self.symbol, self.timeframe),
            StrategyBTrendPullback(self.symbol, self.timeframe),
            StrategyCMeanReversion(self.symbol, self.timeframe)
        ]
        return strategies
        
    def get_all_strategies(self) -> List[BaseStrategy]:
        return self._strategies
        
    def disable_strategy(self, strategy_id: str, reason: str):
        for s in self._strategies:
            if s.__class__.__name__ == strategy_id:
                s.disable(reason)
