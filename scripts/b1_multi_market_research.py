import pandas as pd
import numpy as np
import os
import time
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator

def analyze_symbol(symbol: str, mapped_symbol: str):
    print(f"Fetching data for {symbol} ({mapped_symbol})...")
    # 30 days of M5 candles = 30 * 24 * 12 = 8640
    df = mt5_client.get_historical_data(mapped_symbol, "M5", 8640)
    
    if df.empty or len(df) < 500:
        return {
            "Market": symbol,
            "Mapped_Symbol": mapped_symbol,
            "Status": "INSUFFICIENT_DATA",
            "Bars Loaded": len(df),
            "Missing Bars %": 100.0,
            "Average Spread (pips)": None,
            "ATR %": None,
            "Session Distribution": None,
            "Regime Distribution": None
        }
        
    df = IndicatorCalculator.add_indicators(df)
    df = df.dropna().copy()
    
    # Calculate Missing Bars % (Gaps > 5 mins during active days)
    # This is a rough estimation. Weekends create huge gaps.
    time_diff = df['time'].diff().dt.total_seconds()
    # If gap is exactly 300s, it's continuous. 
    # Let's count gaps between 300s and 48 hours (to exclude weekends).
    intra_week_gaps = time_diff[(time_diff > 300) & (time_diff < 172800)]
    missing_bars = (intra_week_gaps / 300 - 1).sum() if not intra_week_gaps.empty else 0
    missing_pct = (missing_bars / (len(df) + missing_bars)) * 100 if len(df) > 0 else 0

    # Average Spread
    avg_spread = df['spread'].mean() if 'spread' in df.columns else 0.0
    
    # ATR %
    atr_pct = (df['atr'] / df['close']).mean() * 100
    
    # Session Distribution
    # Assuming MT5 server time is roughly UTC+2/UTC+3
    df['hour'] = df['time'].dt.hour
    asian = df[(df['hour'] >= 0) & (df['hour'] < 8)]
    london = df[(df['hour'] >= 8) & (df['hour'] < 16)]
    ny = df[(df['hour'] >= 16) & (df['hour'] < 24)]
    
    total = len(df)
    sess_dist = f"Asian {len(asian)/total:.0%}, London {len(london)/total:.0%}, NY {len(ny)/total:.0%}"
    
    # Regime Distribution (Vectorized version of RegimeDetector)
    df['avg_atr'] = df['atr'].rolling(50).mean()
    df['is_trending'] = df['adx'] > 25
    
    df['trend_state'] = 'RANGING'
    cond_up = df['is_trending'] & (df['plus_di'] > df['minus_di']) & (df['ema50_slope'] > 0.5)
    cond_down = df['is_trending'] & (df['minus_di'] > df['plus_di']) & (df['ema50_slope'] < -0.5)
    
    df.loc[cond_up, 'trend_state'] = 'TRENDING_UP'
    df.loc[cond_down, 'trend_state'] = 'TRENDING_DOWN'
    
    trend_counts = df['trend_state'].value_counts(normalize=True)
    
    reg_dist = []
    for state, pct in trend_counts.items():
        if pct > 0.05: # only show > 5%
            reg_dist.append(f"{state} {pct:.0%}")
    reg_dist_str = ", ".join(reg_dist)
    
    return {
        "Market": symbol,
        "Mapped_Symbol": mapped_symbol,
        "Status": "OK",
        "Bars Loaded": len(df),
        "Missing Bars %": round(missing_pct, 2),
        "Average Spread (pips)": round(avg_spread, 2),
        "ATR %": round(atr_pct, 4),
        "Session Distribution": sess_dist,
        "Regime Distribution": reg_dist_str
    }

def main():
    print("Starting B1.1: Multi-Market Research Audit...")
    
    if not mt5_client.connect():
        print("Failed to connect to MT5. Exiting.")
        return
        
    symbols_map = {
        "XAUUSD": "XAUUSDm",
        "BTCUSD": "BTCUSDm",
        "ETHUSD": "ETHUSDm",
        "NAS100": "USTECm",
        "US30": "US30m",
        "EURUSD": "EURUSDm",
        "GBPUSD": "GBPUSDm",
        "USDJPY": "USDJPYm"
    }
    
    results = []
    for sym, mapped in symbols_map.items():
        res = analyze_symbol(sym, mapped)
        results.append(res)
        
    mt5_client.disconnect()
    
    df = pd.DataFrame(results)
    
    os.makedirs("results", exist_ok=True)
    out_path = "results/market_research_audit.csv"
    df.to_csv(out_path, index=False)
    df.to_csv("results/market_research.csv", index=False)
    
    print(f"\nResearch completed successfully. Results saved to {out_path}")
    print("\n--- Audit Summary ---")
    print(df.to_string(index=False))

if __name__ == "__main__":
    main()
