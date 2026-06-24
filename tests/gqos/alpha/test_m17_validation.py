import pandas as pd
import numpy as np


from gqos.alpha.validation.metrics import AlphaValidationMetrics
from gqos.alpha.validation.matrix import AlphaMatrix
from gqos.alpha.validation.framework import ChampionChallengerFramework, WalkForwardRanker

def test_execution_lag_forward_return():
    price_df = pd.DataFrame({
        "open": [100.0, 101.0, 102.0, 103.0],
        "close": [100.5, 101.5, 102.5, 103.5]
    })
    
    fwd_ret = AlphaValidationMetrics.generate_forward_returns(price_df, method="open_to_close", horizon=1)
    
    # At index 0 (t=0):
    # Exec at t=1 open (101.0). Exit at t=1 close (101.5). Return = (101.5 - 101.0) / 101.0 = 0.00495...
    assert np.isclose(fwd_ret.iloc[0], (101.5 - 101.0) / 101.0)
    
    # method="close_to_close_lag1"
    fwd_ret_close = AlphaValidationMetrics.generate_forward_returns(price_df, method="close_to_close_lag1", horizon=1)
    
    # At index 0 (t=0):
    # Exec at t=1 close (101.5). Exit at t=2 close (102.5). Return = (102.5 - 101.5) / 101.5 = 0.00985...
    assert np.isclose(fwd_ret_close.iloc[0], (102.5 - 101.5) / 101.5)

def test_ic_and_rank_ic():
    # Known correlation
    forecasts = pd.Series([0.1, 0.5, 0.9, -0.2, -0.8])
    returns = pd.Series([0.01, 0.05, 0.10, -0.02, -0.09])
    
    ic = AlphaValidationMetrics.calculate_ic(forecasts, returns)
    assert ic > 0.9 # Should be highly correlated
    
    rank_ic = AlphaValidationMetrics.calculate_rank_ic(forecasts, returns)
    # The rank order of forecasts is exact same as returns, so rank IC = 1.0
    assert np.isclose(rank_ic, 1.0)

def test_ic_stability_and_autocorr():
    ic_series = pd.Series([0.1, 0.15, 0.05, 0.1, 0.12])
    stab = AlphaValidationMetrics.calculate_ic_stability(ic_series)
    assert stab > 0
    assert stab == float(ic_series.mean() / ic_series.std())
    
    forecasts = pd.Series([1.0, 0.9, 0.8, 0.7, 0.6]) # perfectly autocorrelated
    autocorr = AlphaValidationMetrics.forecast_autocorrelation(forecasts, lag=1)
    assert np.isclose(autocorr, 1.0)

def test_alpha_decay_curve():
    price_df = pd.DataFrame({
        "open": [100, 101, 102, 103, 104, 105],
        "close": [100.5, 101.5, 102.5, 103.5, 104.5, 105.5]
    })
    forecasts = pd.Series([0.5, 0.5, 0.5, 0.5, 0.5, 0.5]) # Constant
    
    decay = AlphaValidationMetrics.alpha_decay_curve(forecasts, price_df, max_horizon=3)
    assert len(decay) == 3
    assert 1 in decay
    assert 3 in decay

def test_cross_model_correlation():
    f1 = pd.Series([1.0, 0.5, 0.0, -0.5, -1.0])
    f2 = f1 * 2 # perfectly correlated
    f3 = f1 * -1 # perfectly inverse correlated
    
    matrix = AlphaMatrix.cross_model_correlation({"f1": f1, "f2": f2, "f3": f3}, method='spearman')
    
    assert np.isclose(matrix.loc["f1", "f2"], 1.0)
    assert np.isclose(matrix.loc["f1", "f3"], -1.0)

def test_champion_challenger_framework():
    f1 = pd.Series([1.0, 0.5, 0.0, -0.5, -1.0])
    f2 = f1 * 2 # highly correlated
    f3 = pd.Series([0.0, -0.5, 1.0, 0.5, 0.0]) # Uncorrelated
    
    framework = ChampionChallengerFramework(corr_threshold=0.8)
    
    # 1. First alpha accepted
    assert framework.evaluate_challenger("alpha_1", f1) == True
    
    # 2. Perfect correlation rejection
    assert framework.evaluate_challenger("alpha_2", f2) == False
    assert len(framework.rejection_log) == 1
    assert framework.rejection_log[0]["status"] == "REJECTED"
    
    # 3. Uncorrelated accepted
    assert framework.evaluate_challenger("alpha_3", f3) == True
    
    # 4. Optional orthogonalization
    assert framework.evaluate_challenger("alpha_4", f2, allow_orthogonalization=True) == True
    assert framework.rejection_log[-1]["status"] == "ACCEPTED_ORTHOGONALIZED"
    assert "alpha_4_ortho" in framework.champions

def test_walk_forward_ranker():
    np.random.seed(42)
    # create 100 bars
    price_df = pd.DataFrame({
        "open": np.linspace(100, 200, 100),
        "close": np.linspace(101, 201, 100)
    })
    
    # Alpha 1: highly predictive (returns are decreasing 1/open[t+1], so we use decreasing alpha)
    a1 = pd.Series(np.linspace(1, 0, 100)) 
    # Alpha 2: random noise
    a2 = pd.Series(np.random.randn(100))
    
    ranker = WalkForwardRanker(folds=5)
    profiles = ranker.evaluate({"a1": a1, "a2": a2}, price_df)
    
    assert len(profiles) == 2
    # a1 should rank higher than a2
    assert profiles[0].alpha_id == "a1"
    assert profiles[1].alpha_id == "a2"

if __name__ == "__main__":
    test_execution_lag_forward_return()
    test_ic_and_rank_ic()
    test_ic_stability_and_autocorr()
    test_alpha_decay_curve()
    test_cross_model_correlation()
    test_champion_challenger_framework()
    test_walk_forward_ranker()
    print("M17 Validation tests passed!")
