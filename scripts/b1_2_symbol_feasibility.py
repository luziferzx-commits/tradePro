import pandas as pd
import numpy as np
import os
import time
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator

def get_symbol_metrics(symbol: str, mapped_symbol: str, symbol_info):
    # Fetch 30 days of M5
    df = mt5_client.get_historical_data(mapped_symbol, "M5", 8640)
    
    if df.empty or len(df) < 500:
        return None
        
    df = IndicatorCalculator.add_indicators(df)
    df = df.dropna().copy()
    
    # Missing Bars
    time_diff = df['time'].diff().dt.total_seconds()
    intra_week_gaps = time_diff[(time_diff > 300) & (time_diff < 172800)]
    missing_bars = (intra_week_gaps / 300 - 1).sum() if not intra_week_gaps.empty else 0
    missing_pct = (missing_bars / (len(df) + missing_bars)) * 100 if len(df) > 0 else 0
    
    # Spread
    avg_spread = df['spread'].mean() if 'spread' in df.columns else 0.0
    
    # ATR & Point math
    point = symbol_info.point if symbol_info else 1e-5
    avg_atr = df['atr'].mean()
    avg_atr_points = avg_atr / point if point > 0 else 1
    
    spread_to_atr_ratio = avg_spread / avg_atr_points if avg_atr_points > 0 else 999.0
    atr_pct = (df['atr'] / df['close']).mean() * 100
    
    # Session dist
    df['hour'] = df['time'].dt.hour
    total = len(df)
    asian_pct = len(df[(df['hour'] >= 0) & (df['hour'] < 8)]) / total
    london_pct = len(df[(df['hour'] >= 8) & (df['hour'] < 16)]) / total
    ny_pct = len(df[(df['hour'] >= 16) & (df['hour'] < 24)]) / total
    
    # Regime dist
    df['avg_atr_50'] = df['atr'].rolling(50).mean()
    df['is_trending'] = df['adx'] > 25
    
    df['trend_state'] = 'RANGING'
    cond_up = df['is_trending'] & (df['plus_di'] > df['minus_di']) & (df['ema50_slope'] > 0.5)
    cond_down = df['is_trending'] & (df['minus_di'] > df['plus_di']) & (df['ema50_slope'] < -0.5)
    
    df.loc[cond_up, 'trend_state'] = 'TRENDING_UP'
    df.loc[cond_down, 'trend_state'] = 'TRENDING_DOWN'
    
    trend_counts = df['trend_state'].value_counts(normalize=True)
    ranging_pct = trend_counts.get('RANGING', 0)
    up_pct = trend_counts.get('TRENDING_UP', 0)
    down_pct = trend_counts.get('TRENDING_DOWN', 0)
    
    return {
        "Market": symbol,
        "Bars Loaded": len(df),
        "Missing Bars %": missing_pct,
        "Avg Spread (pts)": avg_spread,
        "Avg ATR (pts)": avg_atr_points,
        "Spread/ATR Ratio": spread_to_atr_ratio,
        "ATR %": atr_pct,
        "Sess_Asian": asian_pct,
        "Sess_London": london_pct,
        "Sess_NY": ny_pct,
        "Reg_Ranging": ranging_pct,
        "Reg_TrendUp": up_pct,
        "Reg_TrendDown": down_pct
    }

def calculate_distance(dist1, dist2):
    return sum(abs(v1 - v2) for v1, v2 in zip(dist1, dist2))

def main():
    print("Starting B1.2: Symbol Feasibility Score...")
    
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
    
    raw_data = {}
    for sym, mapped in symbols_map.items():
        info = mt5_client.get_symbol_info(mapped)
        res = get_symbol_metrics(sym, mapped, info)
        if res:
            raw_data[sym] = res
            
    mt5_client.disconnect()
    
    if "XAUUSD" not in raw_data:
        print("Error: Baseline XAUUSD data missing.")
        return
        
    base = raw_data["XAUUSD"]
    base_sess = (base["Sess_Asian"], base["Sess_London"], base["Sess_NY"])
    base_reg = (base["Reg_Ranging"], base["Reg_TrendUp"], base["Reg_TrendDown"])
    base_atr = base["ATR %"]
    
    scored_results = []
    
    for sym, data in raw_data.items():
        # Session similarity (lower distance = better)
        sym_sess = (data["Sess_Asian"], data["Sess_London"], data["Sess_NY"])
        sess_dist = calculate_distance(sym_sess, base_sess)
        
        # Regime similarity
        sym_reg = (data["Reg_Ranging"], data["Reg_TrendUp"], data["Reg_TrendDown"])
        reg_dist = calculate_distance(sym_reg, base_reg)
        
        # Volatility similarity
        vol_dist = abs(data["ATR %"] - base_atr)
        
        # Data Quality (0 to 100)
        # assuming max bars expected ~8440
        data_quality = min(100, (data["Bars Loaded"] / 8440.0) * 100) - data["Missing Bars %"]
        
        # We need to construct a Feasibility Score (0-100)
        # 1. Spread/ATR Ratio penalty (Spread taking a chunk of the move)
        # A ratio of 0.1 means spread is 10% of a 14-period ATR move. Excellent.
        # A ratio of 0.5 means spread is 50% of an ATR move. Very bad.
        spread_score = max(0, 100 - (data["Spread/ATR Ratio"] * 300))
        
        # 2. Similarity Penalty
        # sess_dist max is ~2.0, reg_dist max is ~2.0
        # vol_dist can be large if crypto (e.g., 0.25 vs 0.12). 
        sim_score = max(0, 100 - (sess_dist * 50) - (reg_dist * 100) - (vol_dist * 200))
        
        final_score = (spread_score * 0.5) + (sim_score * 0.3) + (data_quality * 0.2)
        
        # If Spread/ATR is absurdly high (like >0.3), penalize heavily
        if data["Spread/ATR Ratio"] > 0.3:
            final_score -= 20
            
        scored_results.append({
            "Market": sym,
            "Feasibility Score": round(final_score, 2),
            "Data Quality": round(data_quality, 2),
            "Spread/ATR Ratio": round(data["Spread/ATR Ratio"], 3),
            "Vol Distance": round(vol_dist, 4),
            "Regime Distance": round(reg_dist, 4),
            "Session Distance": round(sess_dist, 4),
            "Raw_ATR_Pct": round(data["ATR %"], 4),
            "Raw_Missing_Pct": round(data["Missing Bars %"], 2)
        })
        
    df_scores = pd.DataFrame(scored_results)
    df_scores = df_scores.sort_values("Feasibility Score", ascending=False).reset_index(drop=True)
    df_scores["Rank"] = df_scores.index + 1
    
    os.makedirs("results", exist_ok=True)
    out_path = "results/market_feasibility_score.csv"
    df_scores.to_csv(out_path, index=False)
    
    print(f"\nResearch completed. Results saved to {out_path}")
    print("\n--- B1.2 Symbol Feasibility Ranking ---")
    cols = ["Rank", "Market", "Feasibility Score", "Spread/ATR Ratio", "Vol Distance", "Regime Distance"]
    print(df_scores[cols].to_string(index=False))

if __name__ == "__main__":
    main()
