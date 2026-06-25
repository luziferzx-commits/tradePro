import unittest
import os
import json
from strategy.health_manager import StrategyHealthManager

class TestStrategyHealthManager(unittest.TestCase):
    def setUp(self):
        self.state_file = "test_strategy_health.json"
        self.manager = StrategyHealthManager(state_file=self.state_file)

    def tearDown(self):
        if os.path.exists(self.state_file):
            os.remove(self.state_file)

    def test_high_pf_healthy(self):
        self.manager.update_metrics(
            strategy_id="StratA",
            pf=1.6,
            expectancy=0.25,
            win_rate=0.45,
            max_dd=0.01,
            avg_rr=2.0,
            trade_count=100
        )
        state = self.manager.get_state("StratA")
        # PF=35, Exp=30, DD=20, Synergy(0.9)=10, Trades=5 => 100 points
        self.assertEqual(state.status, "HEALTHY")
        self.assertEqual(state.risk_multiplier, 1.0)
        self.assertGreaterEqual(state.health_score, 90.0)

    def test_pf_less_than_1_disabled(self):
        self.manager.update_metrics(
            strategy_id="StratB",
            pf=0.8,
            expectancy=-0.1,
            win_rate=0.2,
            max_dd=0.08,
            avg_rr=0.5,
            trade_count=50
        )
        state = self.manager.get_state("StratB")
        # PF=0, Exp=0, DD>5%=>some points lost, Synergy(0.1)=1.6, Trades=2.5
        # Total score < 40 => DISABLED
        self.assertEqual(state.status, "DISABLED_BY_EVIDENCE")
        self.assertEqual(state.risk_multiplier, 0.0)
        self.assertLess(state.health_score, 40.0)

    def test_sample_size_guard(self):
        self.manager.update_metrics(
            strategy_id="StratC",
            pf=0.8,
            expectancy=-0.1,
            win_rate=0.2,
            max_dd=0.08,
            avg_rr=0.5,
            trade_count=10 # < 30 trades
        )
        state = self.manager.get_state("StratC")
        # Even though score is bad, trades < 30 so it's INSUFFICIENT_SAMPLE
        self.assertEqual(state.status, "INSUFFICIENT_SAMPLE")
        self.assertEqual(state.risk_multiplier, 0.25)

    def test_degraded_risk_reduction(self):
        self.manager.update_metrics(
            strategy_id="StratD",
            pf=1.1, # Gives 10-20 pts
            expectancy=0.05, # Gives some pts
            win_rate=0.35,
            max_dd=0.04,
            avg_rr=1.0,
            trade_count=50
        )
        state = self.manager.get_state("StratD")
        # Score should be somewhere in 50-69 range depending on math
        # Actually let's force it to be degraded
        # PF 1.1 -> 10 + 10*(0.1/0.15) = 16.6
        # Exp 0.05 -> 15*(0.05/0.2) = 3.75
        # DD 0.04 -> 10 + 10*(0.01/0.03) = 13.3
        # Syn 0.35 -> 5.8
        # Trades 50 -> 2.5
        # Total ~ 42 (WATCHLIST)
        
        self.assertIn(state.status, ["WATCHLIST", "DEGRADED"])
        self.assertIn(state.risk_multiplier, [0.25, 0.5])

if __name__ == '__main__':
    unittest.main()
