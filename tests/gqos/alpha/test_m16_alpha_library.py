import pandas as pd
import numpy as np
from decimal import Decimal

from gqos.alpha.manifest import FeatureManifest
from gqos.alpha.library.features import (
    RollingZScoreFeature, MovingAverageFeature, MacdFeature,
    RsiFeature, AtrFeature, BollingerBandsFeature, DonchianChannelFeature
)
from gqos.alpha.library.models.momentum import MomentumPack
from gqos.alpha.library.models.reversion import MeanReversionPack
from gqos.alpha.library.models.breakout import BreakoutPack
from gqos.alpha.library.models.volatility import VolatilityPack
from gqos.alpha.ensemble import StaticWeightEnsemble
from gqos.alpha.library.analytics import AlphaAnalytics, AlphaBenchmarkSuite

from gqos.messaging.bus import LocalEventBus
from gqos.accounting.engine import AccountingEngine
from gqos.portfolio.manager import PortfolioManager
from gqos.backtest.engine import EventDrivenBacktester
from gqos.backtest.execution import MockExecutionHandler
from gqos.backtest.friction import FixedBpsSlippage
from gqos.backtest.results import BacktestResult, calculate_backtest_metrics

# Mocks for backtester
class MockFeeModel:
    def calculate_fee(self, symbol, direction, quantity, execution_price):
        return Decimal('0'), "USD"

class MockFxConverter:
    def convert(self, amount, from_curr, to_curr):
        return amount

def generate_mock_data(periods=1000):
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=periods, freq="D")
    
    # Random walk with slight upward drift
    returns = np.random.normal(0.0005, 0.015, periods)
    price_path = 100.0 * np.exp(np.cumsum(returns))
    
    # Add High/Low noise
    high = price_path * (1 + np.random.uniform(0.001, 0.01, periods))
    low = price_path * (1 - np.random.uniform(0.001, 0.01, periods))
    
    return pd.DataFrame({
        "close": price_path,
        "high": high,
        "low": low
    }, index=dates)

def test_alpha_library_and_benchmark():
    df = generate_mock_data()
    
    # 1. Compute Features (Lazy DAG simulation)
    # MACD
    macd_feat = MacdFeature("macd_raw")
    macd = macd_feat.compute(df, {})
    
    macd_z_feat = RollingZScoreFeature("macd_zscore", "macd_raw", window=20)
    macd_zscore = macd_z_feat.compute(df, {"macd_raw": macd})
    
    # SMA
    sma_f_feat = MovingAverageFeature("sma_fast", window=20, ma_type="SMA")
    sma_fast = sma_f_feat.compute(df, {})
    
    sma_s_feat = MovingAverageFeature("sma_slow", window=50, ma_type="SMA")
    sma_slow = sma_s_feat.compute(df, {})
    
    # RSI
    rsi_feat = RsiFeature("rsi", window=14)
    rsi = rsi_feat.compute(df, {})
    
    # ATR
    atr_feat = AtrFeature("atr", window=14)
    atr = atr_feat.compute(df, {})
    
    atr_z_feat = RollingZScoreFeature("atr_zscore", "atr", window=20)
    atr_zscore = atr_z_feat.compute(df, {"atr": atr})
    
    # BB
    bb_feat = BollingerBandsFeature("bb_pct_b", window=20)
    bb_pct_b = bb_feat.compute(df, {})
    
    # Donchian
    donchian_feat = DonchianChannelFeature("donchian_pos", window=20)
    donchian_pos = donchian_feat.compute(df, {})
    
    feature_dict = {
        "macd_zscore": macd_zscore,
        "sma_fast": sma_fast,
        "sma_slow": sma_slow,
        "rsi": rsi,
        "atr_zscore": atr_zscore,
        "bb_pct_b": bb_pct_b,
        "donchian_pos": donchian_pos
    }
    
    manifest = FeatureManifest(
        dataset_hash="m16_run_1", 
        feature_hash="hash", 
        dependency_hash="hash", 
        cache_hash="hash", 
        execution_order=["macd_zscore"], 
        engine_version="1.0"
    )
    
    # 2. Run Alpha Models
    momentum = MomentumPack()
    mom_forecast = momentum.generate_forecasts("mock_ds", manifest, feature_dict)
    assert not mom_forecast.frame['score'].isna().any()
    
    reversion = MeanReversionPack()
    rev_forecast = reversion.generate_forecasts("mock_ds", manifest, feature_dict)
    assert not rev_forecast.frame['score'].isna().any()
    
    breakout = BreakoutPack()
    brk_forecast = breakout.generate_forecasts("mock_ds", manifest, feature_dict)
    assert not brk_forecast.frame['score'].isna().any()
    
    volatility = VolatilityPack()
    vol_forecast = volatility.generate_forecasts("mock_ds", manifest, feature_dict)
    assert not vol_forecast.frame['score'].isna().any()
    
    # 3. Alpha Analytics Test (M16D)
    dist = AlphaAnalytics.forecast_distribution(mom_forecast.frame['score'])
    assert len(dist) == 10
    
    density = AlphaAnalytics.signal_density(rev_forecast.frame['score'])
    assert density >= 0.0 and density <= 1.0
    
    turnover = AlphaAnalytics.forecast_turnover(brk_forecast.frame['score'])
    assert turnover >= 0.0
    
    hist_df = AlphaAnalytics.feature_importance_history(rev_forecast)
    assert not hist_df.empty
    assert "rsi" in hist_df.columns
    
    # 4. Ensemble
    weights = {
        momentum.alpha_id: 0.4,
        reversion.alpha_id: 0.3,
        breakout.alpha_id: 0.2,
        volatility.alpha_id: 0.1
    }
    ensemble = StaticWeightEnsemble(weights)
    forecast_dict = {
        momentum.alpha_id: mom_forecast,
        reversion.alpha_id: rev_forecast,
        breakout.alpha_id: brk_forecast,
        volatility.alpha_id: vol_forecast
    }
    final_forecast = ensemble.blend(forecast_dict)
    
    # 5. Backtest
    bus = LocalEventBus(None) # Muted logger
    acc = AccountingEngine(bus, MockFeeModel(), MockFxConverter())
    port = PortfolioManager("SimPort", Decimal('100000.0'))
    
    bt = EventDrivenBacktester(bus, None, acc, port)
    
    # Wire mock execution
    def pf(sym): return Decimal(str(df.loc[df.index[df.index <= pd.Timestamp(bt.system_time, unit='s')][-1], "close"])) if bt.system_time > 0 else Decimal('100.0')
    exe = MockExecutionHandler(bus, FixedBpsSlippage(0.0), pf)
    bt._execution_handler = exe
    
    # Create price df for backtester
    price_df = pd.DataFrame({"close": df["close"]})
    
    bt.run_simulation(final_forecast.frame, price_df, "AAPL")
    
    eq = pd.Series(bt.equity_curve)
    metrics = calculate_backtest_metrics(eq)
    
    btr = BacktestResult(equity_curve=eq, trade_log=pd.DataFrame(), metrics=metrics)
    
    # Benchmark Evaluation
    eval_report = AlphaBenchmarkSuite.evaluate_model("Final_Ensemble", final_forecast, btr)
    
    assert "hit_rate" in eval_report["metrics"]
    assert "profit_factor" in eval_report["metrics"]
    assert "distribution" in eval_report

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.ERROR)
    test_alpha_library_and_benchmark()
    print("M16 Alpha Library tests passed!")
