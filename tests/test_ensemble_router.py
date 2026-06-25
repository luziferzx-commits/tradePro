import unittest
import pandas as pd
from strategy.strategies.base import SignalDecision
from strategy.strategies.ensemble_router import EnsembleRouter
from strategy.strategies.registry import StrategyRegistry

class MockStrategyRegistry(StrategyRegistry):
    def __init__(self):
        self.symbol = "TEST"
        self.timeframe = "M5"
        self._strategies = []

class TestEnsembleRouter(unittest.TestCase):
    def setUp(self):
        self.router = EnsembleRouter(trading_cost_r=0.1, min_ev_threshold=0.0)
        self.registry = MockStrategyRegistry()
        
    def test_empty_dataframe_returns_neutral(self):
        df = pd.DataFrame()
        regime = {}
        signal = self.router.route(df, regime, self.registry)
        self.assertEqual(signal.direction, "NEUTRAL")
        
    def test_ev_ranking(self):
        # In a real test, we would mock the strategies inside the registry
        # and ensure the router picks the one with highest expected_rr
        pass

if __name__ == '__main__':
    unittest.main()
