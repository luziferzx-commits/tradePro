import pytest
import numpy as np
import pandas as pd

from gqos.portfolio.manifest import PortfolioManifest
from gqos.portfolio.lifecycle import AlphaLifecycleManager, AlphaState
from gqos.portfolio.health import AlphaHealthScore
from gqos.portfolio.capacity import AlphaCapacityTracker
from gqos.portfolio.optimization.correlation import PearsonCorrelation
from gqos.portfolio.optimization.hrp import HierarchicalRiskParity
from gqos.portfolio.allocation import EqualWeightAllocator, FractionalKellyAllocator
from gqos.portfolio.router import ShadowRouter
from gqos.portfolio.stress import PortfolioStressTest

def test_alpha_health_score_and_drift():
    metrics = {
        'rolling_sharpe': 1.5,
        'max_drawdown': 0.10, # 10%
        'pbo': 0.1,
        'feature_drift': 0.5 # Moderate drift
    }
    
    score = AlphaHealthScore.calculate(metrics)
    # Base 100
    # DD > 0.05 -> -10
    # Drift > 0.3 -> -15
    # Total = 75
    assert score == 75.0
    
    # Severe drift
    metrics['feature_drift'] = 0.9
    score_severe = AlphaHealthScore.calculate(metrics)
    # Drift > 0.8 -> -40
    # DD > 0.05 -> -10
    # Total = 50
    assert score_severe == 50.0

def test_alpha_lifecycle_and_shadow_routing():
    lm = AlphaLifecycleManager()
    
    lm.register_candidate("A1")
    lm.transition("A1", AlphaState.CHALLENGER, "Factory Promoted", "2026-06-24")
    
    lm.register_candidate("A2")
    lm.transition("A2", AlphaState.CHAMPION, "Manual Approval", "2026-06-24")
    
    lm.register_candidate("A3")
    lm.transition("A3", AlphaState.WATCHLIST, "Performance Decay", "2026-06-24")
    
    router = ShadowRouter(lm)
    
    target_allocs = {"A1": 1000, "A2": 1000, "A3": 1000, "A4": 1000}
    routed = router.route_allocations(target_allocs)
    
    assert routed["A1"] == 0.0 # Challenger is shadow
    assert routed["A2"] == 1000.0 # Champion is live
    assert routed["A3"] == 500.0 # Watchlist is decayed (50% in our logic)
    assert routed["A4"] == 0.0 # Unknown is 0

def test_capital_allocators():
    returns_df = pd.DataFrame({
        "A1": np.random.normal(0.001, 0.01, 252),
        "A2": np.random.normal(0.0005, 0.02, 252)
    })
    
    base_weights = {"A1": 0.6, "A2": 0.4}
    target_cap = 10000.0
    
    # Equal Weight
    eq = EqualWeightAllocator()
    eq_alloc = eq.allocate(base_weights, returns_df, target_cap)
    assert eq_alloc["A1"] == 5000.0
    assert eq_alloc["A2"] == 5000.0
    
    # Fractional Kelly
    fk = FractionalKellyAllocator(fraction=0.5)
    fk_alloc = fk.allocate(base_weights, returns_df, target_cap)
    assert "A1" in fk_alloc
    assert fk_alloc["A1"] > 0

def test_hrp_deterministic_tree():
    np.random.seed(42)
    # A1, A2 correlated. A3 independent.
    a1 = np.random.normal(0, 1, 100)
    a2 = a1 + np.random.normal(0, 0.1, 100)
    a3 = np.random.normal(0, 1, 100)
    
    returns_df = pd.DataFrame({"A1": a1, "A2": a2, "A3": a3})
    
    hrp = HierarchicalRiskParity()
    weights = hrp.optimize(returns_df)
    
    # Due to high correlation, A1 and A2 should share roughly half the weight, and A3 the other half
    assert abs((weights["A1"] + weights["A2"]) - weights["A3"]) < 0.2
    
    # Determinism
    weights2 = hrp.optimize(returns_df)
    assert weights == weights2

def test_portfolio_stress_test():
    np.random.seed(42)
    returns_df = pd.DataFrame({
        "A1": np.random.normal(0, 0.01, 252),
        "A2": np.random.normal(0, 0.01, 252)
    })
    
    allocations = {"A1": 5000.0, "A2": 5000.0}
    
    shock_vol = PortfolioStressTest.apply_shock(allocations, returns_df, "volatility_x2")
    shock_corr = PortfolioStressTest.apply_shock(allocations, returns_df, "correlation_1")
    
    assert shock_vol < 0
    assert shock_corr < 0

def test_portfolio_manifest():
    m1 = PortfolioManifest(
        portfolio_id="P1",
        timestamp="2026-06-24",
        alpha_versions={"A2": "hash2", "A1": "hash1"}, # Unordered
        weights={"A2": 0.4, "A1": 0.6},
        hrp_tree_hash="hrp_hash",
        kelly_fraction=0.5,
        regime="Bull",
        validation_hash="val_hash"
    )
    
    m2 = PortfolioManifest(
        portfolio_id="P1",
        timestamp="2026-06-24",
        alpha_versions={"A1": "hash1", "A2": "hash2"}, # Ordered
        weights={"A1": 0.6, "A2": 0.4},
        hrp_tree_hash="hrp_hash",
        kelly_fraction=0.5,
        regime="Bull",
        validation_hash="val_hash"
    )
    
    assert m1.calculate_hash() == m2.calculate_hash()

if __name__ == "__main__":
    pytest.main(["-v", __file__])
