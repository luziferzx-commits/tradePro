import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock

from gqos.research.ml.features import FractionalDifferentiation, AutoFD
from gqos.research.ml.labels import TripleBarrierMethod
from gqos.research.ml.validation import CombinatorialPurgedCV, ValidationManifest
from gqos.research.statistics.bootstrap import BootstrapEngine
from gqos.research.statistics.pbo import ProbabilityOfBacktestOverfitting
from gqos.research.statistics.hypothesis import FalseDiscoveryRate, RealityCheck, SuperiorPredictiveAbility
from gqos.research.statistics.metrics import InstitutionalMetrics

def test_fractional_differentiation():
    # Simple sine wave + trend
    t = np.linspace(0, 100, 1000)
    series = pd.Series(np.sin(t) + t * 0.1)
    
    # Apply fractional differentiation
    fd_series = FractionalDifferentiation.frac_diff_ffd(series, d=0.4, thres=1e-4)
    
    # Output should be shorter (due to fixed window truncation)
    assert len(fd_series.dropna()) < len(series)
    # Output shouldn't be all NaNs
    assert not fd_series.dropna().empty

def test_auto_fd():
    np.random.seed(42)
    # Generate non-stationary random walk
    series = pd.Series(np.random.normal(0, 1, 500).cumsum())
    
    optimal_d = AutoFD.select_d(series, max_d=1.0, step=0.1, p_value=0.05)
    
    # Optimal d should be between 0 and 1 (usually ~0.4 - 0.6 for random walks)
    assert 0 < optimal_d <= 1.0

def test_triple_barrier_method():
    close = pd.Series([100, 101, 105, 95, 110], index=pd.date_range("2020-01-01", periods=5))
    t_events = close.index[0:1] # Event at day 0
    target = pd.Series([0.02, 0.02, 0.02, 0.02, 0.02], index=close.index) # 2% volatility
    t1 = pd.Series([close.index[-1]], index=t_events) # Vertical barrier at the end
    
    # PT=1, SL=1 => 2% up or 2% down
    events = TripleBarrierMethod.get_events(close, t_events, pt_sl=[1.0, 1.0], target=target, min_ret=0.001, t1=t1)
    
    assert len(events) == 1
    # Day 0: 100
    # Day 1: 101 (1%)
    # Day 2: 105 (5%) -> Hits PT!
    assert events.iloc[0]['hit_type'] == 'pt'
    assert events.iloc[0]['first_touch'] == close.index[2]
    assert events.iloc[0]['holding_time'].days == 2

def test_combinatorial_purged_cv():
    X = pd.DataFrame(np.random.randn(100, 2))
    # N=6, k=2 => Combinations C(6,2) = 15 splits
    cv = CombinatorialPurgedCV(n_groups=6, k_test_groups=2, purge_pct=0.01, embargo_pct=0.01)
    
    splits = list(cv.split(X))
    assert len(splits) == 15
    
    # Check no overlap
    for train_idx, test_idx in splits:
        assert len(np.intersect1d(train_idx, test_idx)) == 0

def test_bootstrap_reproducibility():
    data_length = 100
    num_samples = 10
    
    idx1 = BootstrapEngine.stationary_bootstrap(data_length, num_samples, seed=42)
    idx2 = BootstrapEngine.stationary_bootstrap(data_length, num_samples, seed=42)
    idx3 = BootstrapEngine.stationary_bootstrap(data_length, num_samples, seed=99)
    
    np.testing.assert_array_equal(idx1, idx2)
    assert not np.array_equal(idx1, idx3)

def test_pbo_calculation():
    # is_metrics shape (num_splits, num_strategies)
    # Simulate a scenario where IS best is always OOS worst
    is_metrics = np.array([
        [1.0, 0.5],
        [0.8, 0.2]
    ])
    oos_metrics = np.array([
        [0.1, 0.9], # Strategy 0 was IS best (1.0), but OOS worst (0.1)
        [0.0, 0.5]  # Strategy 0 was IS best (0.8), but OOS worst (0.0)
    ])
    
    pbo = ProbabilityOfBacktestOverfitting.calculate_cscv(is_metrics, oos_metrics)
    
    # In both splits, the optimal IS strategy performed below median OOS
    assert pbo == 1.0 

def test_hypothesis_fdr_and_spa():
    # 1. FDR
    p_values = np.array([0.001, 0.01, 0.04, 0.1, 0.5])
    discoveries = FalseDiscoveryRate.benjamini_hochberg(p_values, alpha=0.05)
    assert np.sum(discoveries) == 2 # 0.001 and 0.01 are true discoveries under B-H
    
    # 2. White's RC & SPA
    # Strategy that perfectly matches benchmark (excess = 0)
    strat_ret = pd.DataFrame({'s1': np.random.normal(0.001, 0.01, 500)})
    bench_ret = strat_ret['s1']
    
    p_white = RealityCheck.white_reality_check(strat_ret, bench_ret, num_bootstraps=100, seed=42)
    p_spa = SuperiorPredictiveAbility.hansen_spa(strat_ret, bench_ret, num_bootstraps=100, seed=42)
    
    # Should not reject null hypothesis (p-value high)
    assert p_white > 0.05
    assert p_spa > 0.05

def test_institutional_metrics():
    sharpe = 1.5
    target_sharpe = 0.0
    
    # Expected Max Sharpe
    trials = np.random.normal(0, 1, 100)
    ems = InstitutionalMetrics.expected_max_sharpe(trials)
    assert ems > 0 # Max of 100 N(0,1) is around 2.5
    
    # Minimum Track Record Length
    # Requires more time if sharpe is closer to target
    mtl_1 = InstitutionalMetrics.min_track_record_length(1.0, target_sharpe=0.0)
    mtl_2 = InstitutionalMetrics.min_track_record_length(0.5, target_sharpe=0.0)
    
    assert mtl_2 > mtl_1 # Lower sharpe needs longer track record to prove significance

def test_validation_manifest():
    manifest = ValidationManifest(
        dataset_hash="d_hash",
        feature_hash="f_hash",
        auto_fd_d=0.45,
        tbm_config={"pt": 1, "sl": 1},
        cpcv_config={"n": 6, "k": 2},
        bootstrap_seed=42,
        pbo=0.1,
        dsr=1.2,
        spa_p_value=0.01,
        reality_check_p_value=0.02
    )
    assert manifest.auto_fd_d == 0.45
    assert manifest.pbo == 0.1

if __name__ == "__main__":
    pytest.main(["-v", __file__])
