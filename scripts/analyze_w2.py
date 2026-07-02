import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

from strategy.market_structure import market_structure
from strategy.liquidity import liquidity_sweep
from strategy.premium_discount import premium_discount
from strategy.edge_scorer import edge_scorer
from strategy.mtf import mtf_context
from strategy.indicators import IndicatorCalculator

def prepare_dataset():
    from data.mt5_client import mt5_client
    if not mt5_client.connect(): return None
    df = mt5_client.get_historical_data("XAUUSDm", "M5", 250000)
    mt5_client.disconnect()
    
    if df is None or df.empty: return None

    df = IndicatorCalculator.add_indicators(df)
    if 'session_score' not in df.columns: df['session_score'] = np.random.randn(len(df))
    if 'trend_score' not in df.columns: df['trend_score'] = np.random.randn(len(df))
    
    df = mtf_context.calculate(df)
    df = market_structure.calculate(df)
    df = liquidity_sweep.calculate(df)
    df = premium_discount.calculate(df)
    df = edge_scorer.calculate(df)
    
    # Filter 
    df = df.dropna(subset=['atr'])
    return df

def run_analysis():
    print("Preparing Full Edge V2 Dataset (approx 3.5 years)...")
    df = prepare_dataset()
    if df is None: return

    train_size = 72000
    test_size = 18000
    step_size = 18000
    
    # W2 Test Slice
    w2_start = (1 * step_size) + train_size
    w2_end = w2_start + test_size
    w2_df = df.iloc[w2_start:w2_end]
    
    # W4 Test Slice
    w4_start = (3 * step_size) + train_size
    w4_end = w4_start + test_size
    w4_df = df.iloc[w4_start:w4_end]
    
    print(f"\\n--- Regime Analysis: W2 (FAIL) vs W4 (PASS) ---")
    print(f"W2 Period: {w2_df['time'].iloc[0]} to {w2_df['time'].iloc[-1]}")
    print(f"W4 Period: {w4_df['time'].iloc[0]} to {w4_df['time'].iloc[-1]}")
    
    # Volatility
    w2_atr_mean = w2_df['atr'].mean()
    w4_atr_mean = w4_df['atr'].mean()
    
    # Trend Strength (Percentage of M5 candles in a strong H1 trend vs ranging)
    w2_trend_pct = (w2_df['h1_struct_trend'] != 'RANGING').mean() * 100
    w4_trend_pct = (w4_df['h1_struct_trend'] != 'RANGING').mean() * 100
    
    # Total Sweeps occurred in this period
    w2_sweeps = w2_df['sweep_swing_high_50'].sum() + w2_df['sweep_swing_low_50'].sum()
    w4_sweeps = w4_df['sweep_swing_high_50'].sum() + w4_df['sweep_swing_low_50'].sum()
    
    print(f"\\nMetric                 | W2 (FAIL)           | W4 (PASS)")
    print("-" * 65)
    print(f"Avg ATR (Volatility)   | {w2_atr_mean:>19.2f} | {w4_atr_mean:>19.2f}")
    print(f"H1 Trending Time %     | {w2_trend_pct:>18.1f}% | {w4_trend_pct:>18.1f}%")
    print(f"Total Sweep Setups     | {w2_sweeps:>19} | {w4_sweeps:>19}")
    
if __name__ == "__main__":
    run_analysis()
