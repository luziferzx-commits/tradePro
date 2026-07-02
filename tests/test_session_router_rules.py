import unittest
import os
import pandas as pd
from strategy.strategies.ensemble_router import EnsembleRouter
from strategy.strategies.registry import StrategyRegistry
from strategy.strategies.base import BaseStrategy, SignalDecision

class DummyBreakoutStrategy(BaseStrategy):
    def generate_signal(self, df: pd.DataFrame, regime: dict) -> SignalDecision:
        sig = self.get_neutral_signal("test")
        sig.direction = "BUY"
        sig.edge_score = 0.5
        sig.expected_rr = 5.0 # Yields positive EV
        sig.status = "APPROVED"
        return sig

class DummyRegistry(StrategyRegistry):
    def __init__(self):
        self.symbol = "TEST"
        self.timeframe = "M5"
        self._strategies = [DummyBreakoutStrategy("TEST", "M5")]
        # Hack the name to match the block condition
        self._strategies[0].__class__.__name__ = "StrategyABreakout"

class TestSessionRouterRules(unittest.TestCase):
    def setUp(self):
        os.environ["SESSION_AWARE_ROUTER"] = "true"
        self.router = EnsembleRouter(trading_cost_r=0.1, min_ev_threshold=0.0)
        self.registry = DummyRegistry()
        self.df = pd.DataFrame({'close': [1,2,3]})

    def test_asia_blocks_breakout_if_not_expanding(self):
        regime = {"volatility": "NORMAL"}
        session_info = {"session_label": "ASIA"}
        signal = self.router.route(self.df, regime, self.registry, session_info=session_info)
        self.assertEqual(signal.direction, "NEUTRAL")

    def test_asia_allows_breakout_if_expanding(self):
        regime = {"volatility": "EXPANDING"}
        session_info = {"session_label": "ASIA"}
        signal = self.router.route(self.df, regime, self.registry, session_info=session_info)
        self.assertEqual(signal.direction, "BUY")

    def test_off_session_blocks_everything(self):
        regime = {"volatility": "EXPANDING"}
        session_info = {"session_label": "OFF_SESSION"}
        signal = self.router.route(self.df, regime, self.registry, session_info=session_info)
        self.assertEqual(signal.direction, "NEUTRAL")

    def test_overlap_penalizes_ev(self):
        regime = {"volatility": "NORMAL"}
        session_info = {"session_label": "LONDON_NY_OVERLAP"}
        signal = self.router.route(self.df, regime, self.registry, session_info=session_info)
        self.assertEqual(signal.direction, "BUY")
        self.assertAlmostEqual(signal.edge_score, 1.15)

if __name__ == '__main__':
    unittest.main()
