from decimal import Decimal
from datetime import datetime, timedelta
import math
from gqos.accounting.attribution import NavSnapshot
from gqos.accounting.risk_metrics import RiskMetricsEngine

def test_synthetic_max_drawdown():
    engine = RiskMetricsEngine()
    t0 = datetime(2026, 1, 1)
    
    # Peak at 100k, drop to 80k (20% DD), recover to 120k, drop to 60k (50% DD)
    snapshots = [
        NavSnapshot(t0, Decimal('100000.0')),
        NavSnapshot(t0 + timedelta(days=1), Decimal('80000.0')),  # 20%
        NavSnapshot(t0 + timedelta(days=2), Decimal('120000.0')), # New peak
        NavSnapshot(t0 + timedelta(days=3), Decimal('60000.0')),  # 50% from 120k
        NavSnapshot(t0 + timedelta(days=4), Decimal('90000.0'))   # recovery
    ]
    
    metrics = engine.calculate_drawdown(snapshots)
    assert metrics.max_drawdown_pct == Decimal('0.5')
    assert metrics.max_duration == timedelta(days=2) # peak at day 2, current is day 4 -> 2 days so far

def test_sharpe_known_return():
    engine = RiskMetricsEngine(annualization_factor=252)
    t0 = datetime(2026, 1, 1)
    
    # Let's create daily returns of exactly +1% every day for 4 days
    snapshots = [
        NavSnapshot(t0, Decimal('100.0')),
        NavSnapshot(t0 + timedelta(days=1), Decimal('101.0')),
        NavSnapshot(t0 + timedelta(days=2), Decimal('102.01')),
        NavSnapshot(t0 + timedelta(days=3), Decimal('103.0301'))
    ]
    
    sharpe = engine.calculate_sharpe_ratio(snapshots)
    assert sharpe == Decimal('0') # Volatility is zero because return is constantly +1%
    
    # What if returns fluctuate?
    snapshots = [
        NavSnapshot(t0, Decimal('100.0')),
        NavSnapshot(t0 + timedelta(days=1), Decimal('102.0')), # +2%
        NavSnapshot(t0 + timedelta(days=2), Decimal('102.0')), # 0%
        NavSnapshot(t0 + timedelta(days=3), Decimal('104.04')) # +2%
    ]
    # returns: 0.02, 0.0, 0.02
    # avg = 0.01333
    # variance = ( (0.02 - 0.0133)^2 + (0 - 0.0133)^2 + (0.02 - 0.0133)^2 ) / 3 = ( 0.0000444 + 0.0001777 + 0.0000444 ) / 3 = 0.0000888
    # std_dev = 0.009428
    # ann_ret = 0.01333 * 252 = 3.36
    # ann_vol = 0.009428 * sqrt(252) = 0.1496
    # Sharpe = 3.36 / 0.1496 = ~22.45
    sharpe = engine.calculate_sharpe_ratio(snapshots)
    assert sharpe > Decimal('20')

def test_sortino_downside_only():
    engine = RiskMetricsEngine()
    t0 = datetime(2026, 1, 1)
    
    snapshots = [
        NavSnapshot(t0, Decimal('100.0')),
        NavSnapshot(t0 + timedelta(days=1), Decimal('102.0')), # +2%
        NavSnapshot(t0 + timedelta(days=2), Decimal('100.98')), # -1%
        NavSnapshot(t0 + timedelta(days=3), Decimal('103.0')) # +2%
    ]
    
    sortino = engine.calculate_sortino_ratio(snapshots, target_return=Decimal('0.0'))
    assert sortino > Decimal('0')

def test_calmar_ratio():
    engine = RiskMetricsEngine(annualization_factor=252)
    t0 = datetime(2026, 1, 1)
    
    snapshots = [
        NavSnapshot(t0, Decimal('100.0')),
        NavSnapshot(t0 + timedelta(days=1), Decimal('110.0')), # +10%
        NavSnapshot(t0 + timedelta(days=2), Decimal('99.0'))   # -10%, peak was 110, drop to 99 = 10% drawdown
    ]
    # Returns: 0.10, -0.10. Avg = 0. Ann_ret = 0
    # Let's make it positive
    snapshots = [
        NavSnapshot(t0, Decimal('100.0')),
        NavSnapshot(t0 + timedelta(days=1), Decimal('110.0')), # +10%
        NavSnapshot(t0 + timedelta(days=2), Decimal('104.5')), # -5%, peak 110 -> 104.5 = 5% DD
        NavSnapshot(t0 + timedelta(days=3), Decimal('114.95')) # +10%
    ]
    # Returns: 0.10, -0.05, 0.10 -> Avg = 0.05 -> Ann Ret = 12.6
    # Max DD = 0.05
    # Calmar = 12.6 / 0.05 = 252
    calmar = engine.calculate_calmar_ratio(snapshots)
    assert round(calmar, 0) == Decimal('252')

def test_rolling_pf_30_day():
    engine = RiskMetricsEngine()
    t0 = datetime(2026, 6, 1)
    
    # events: (timestamp, pnl)
    events = [
        (t0 - timedelta(days=40), Decimal('1000.0')), # Out of 30 day window
        (t0 - timedelta(days=20), Decimal('500.0')),  # Inside
        (t0 - timedelta(days=10), Decimal('-200.0')), # Inside
        (t0, Decimal('300.0'))                        # Inside
    ]
    
    # In window: gross profit = 800, gross loss = 200 -> PF = 4.0
    pf = engine.calculate_rolling_profit_factor(events, window_days=30)
    assert pf == Decimal('4.0')

def test_zero_volatility_handled():
    engine = RiskMetricsEngine()
    t0 = datetime(2026, 1, 1)
    snapshots = [
        NavSnapshot(t0, Decimal('100.0')),
        NavSnapshot(t0 + timedelta(days=1), Decimal('101.0')),
        NavSnapshot(t0 + timedelta(days=2), Decimal('102.01'))
    ]
    sharpe = engine.calculate_sharpe_ratio(snapshots)
    assert sharpe == Decimal('0')

def test_zero_drawdown_handled():
    engine = RiskMetricsEngine()
    t0 = datetime(2026, 1, 1)
    snapshots = [
        NavSnapshot(t0, Decimal('100.0')),
        NavSnapshot(t0 + timedelta(days=1), Decimal('101.0'))
    ]
    calmar = engine.calculate_calmar_ratio(snapshots)
    assert calmar == Decimal('0')

def test_zero_loss_pf_handled():
    engine = RiskMetricsEngine()
    t0 = datetime(2026, 1, 1)
    events = [
        (t0, Decimal('500.0')),
        (t0 + timedelta(days=1), Decimal('300.0'))
    ]
    pf = engine.calculate_rolling_profit_factor(events, window_days=30)
    assert pf == Decimal('99999.0')

def test_deterministic_replay():
    engine = RiskMetricsEngine(annualization_factor=365) # test crypto configuration
    assert engine.annualization_factor == 365
    
    t0 = datetime(2026, 1, 1)
    snapshots = [
        NavSnapshot(t0, Decimal('10000.0')),
        NavSnapshot(t0 + timedelta(days=1), Decimal('11000.0')),
        NavSnapshot(t0 + timedelta(days=2), Decimal('9900.0')),
    ]
    dd = engine.calculate_drawdown(snapshots)
    assert dd.max_drawdown_pct == Decimal('0.1')
    assert dd.max_duration == timedelta(days=1)

if __name__ == "__main__":
    test_synthetic_max_drawdown()
    test_sharpe_known_return()
    test_sortino_downside_only()
    test_calmar_ratio()
    test_rolling_pf_30_day()
    test_zero_volatility_handled()
    test_zero_drawdown_handled()
    test_zero_loss_pf_handled()
    test_deterministic_replay()
    print("M10D Risk Metrics tests passed!")
