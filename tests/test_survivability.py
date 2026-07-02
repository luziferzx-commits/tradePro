"""tests/test_survivability.py"""
import numpy as np
from risk.monte_carlo import MonteCarloSimulator
from risk.risk_of_ruin import RiskOfRuinCalculator
from risk.portfolio_drawdown_guard import PortfolioDrawdownGuard

def test_monte_carlo_simulator_basic():
    returns = [1.0, -1.0, 2.0, -1.0]
    paths = MonteCarloSimulator.simulate(returns, n_simulations=10, n_trades=5)
    assert paths.shape == (10, 5)
    
def test_monte_carlo_drawdowns():
    paths = np.array([
        [1.0, 0.0, -2.0, -1.0],
        [-1.0, -2.0, -1.0, 1.0]
    ])
    drawdowns = MonteCarloSimulator.calculate_drawdowns(paths)
    assert drawdowns[0] == 3.0
    assert drawdowns[1] == 2.0

def test_risk_of_ruin_calculations():
    drawdowns = np.array([10.0, 25.0, 50.0, 60.0])
    prob_20 = RiskOfRuinCalculator.calculate_ruin_probability(drawdowns, 20.0)
    assert prob_20 == 0.75
    prob_50 = RiskOfRuinCalculator.calculate_ruin_probability(drawdowns, 50.0)
    assert prob_50 == 0.50
    
def test_worst_case_drawdown():
    drawdowns = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    worst = RiskOfRuinCalculator.expected_worst_case_drawdown(drawdowns, 100.0)
    assert worst == 50.0
    
def test_loss_streak_probability():
    returns = [-1.0, -1.0, -1.0]
    prob = RiskOfRuinCalculator.calculate_loss_streak_probability(returns, streak_length=2, n_simulations=10, n_trades=5)
    assert prob == 1.0
    
    returns_wins = [2.0, 1.0]
    prob_wins = RiskOfRuinCalculator.calculate_loss_streak_probability(returns_wins, streak_length=2, n_simulations=10, n_trades=5)
    assert prob_wins == 0.0

def test_portfolio_drawdown_guard_fail_open(monkeypatch):
    import MetaTrader5 as mt5
    monkeypatch.setattr(mt5, "account_info", lambda: None)
    safe, reason = PortfolioDrawdownGuard.is_safe()
    assert safe is True
    assert "check_failed" in reason

def test_apply_slippage_shock():
    r = [2.0, -1.0, 1.0]
    s = RiskOfRuinCalculator.apply_slippage_shock(r, 0.1)
    assert s == [1.9, -1.1, 0.9]

def test_apply_bad_regime_shock():
    # Set seed to force a winner to become loser if possible, but easier to just check it runs
    np.random.seed(42)
    r = [2.0, 2.0, 2.0, 2.0, 2.0]
    s = RiskOfRuinCalculator.apply_bad_regime_shock(r, 1.0) # 100% chance to flip
    assert s == [-1.0, -1.0, -1.0, -1.0, -1.0]

def test_apply_loss_streak_shock():
    r = [2.0, 1.0]
    s = RiskOfRuinCalculator.apply_loss_streak_shock(r, 3)
    assert s == [-1.0, -1.0, -1.0, 2.0, 1.0]

def test_apply_worst_case_bootstrap():
    r = [-2.0, -1.0, 0.5, 1.0, 2.0]
    # bottom 40% of 5 is 2 items -> [-2.0, -1.0]
    s = RiskOfRuinCalculator.apply_worst_case_bootstrap(r, 0.40)
    assert s == [-2.0, -1.0]
