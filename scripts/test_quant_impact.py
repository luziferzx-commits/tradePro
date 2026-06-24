import pandas as pd
import numpy as np
import MetaTrader5 as mt5
from config.settings import settings
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator
from strategy.market_score import MarketScoreCalculator
from market.regime_detector import RegimeDetector
from strategy.scorer import MultiScorer
from ml.predictor import ml_predictor

def run_diagnostics():
    symbol = "XAUUSDm"
    timeframe = "M5"
    num_candles = 2000 # Last ~1 week of M5 data
    
    if not mt5_client.connect():
        print("Failed to connect to MT5")
        return
        
    print(f"Fetching {num_candles} candles for {symbol}...")
    df = mt5_client.get_historical_data(symbol, timeframe, num_candles)
    if df is None or df.empty:
        print("No data fetched.")
        return
        
    df = IndicatorCalculator.add_indicators(df)
    
    stats = {
        "candles_checked": 0,
        "indicators_pass": 0,
        "regime_pass": 0,
        "quant_pass": 0,
        "ml_pass": 0,
        "simulated_orders": 0,
        "quant_scores": [],
        "ml_probs": []
    }
    
    print("Running Pipeline Simulation over historical data...")
    
    # We need at least 50 candles for indicators to warm up
    for i in range(100, len(df)):
        df_slice = df.iloc[:i+1].copy()
        
        stats["candles_checked"] += 1
        stats["indicators_pass"] += 1 # assumed
        
        regime = RegimeDetector.detect(df_slice)
        stats["regime_pass"] += 1
        
        market_score = MarketScoreCalculator.calculate(df_slice, regime)
        final_dir = market_score['final_direction']
        
        # We want to track quant score regardless if it passed or not
        stats["quant_scores"].append(market_score['final_score'])
        
        if final_dir == "NEUTRAL":
            continue
            
        stats["quant_pass"] += 1
        
        # Build features for ML Predictor
        current_candle_time = df_slice['time'].iloc[-1]
        indicators = IndicatorCalculator.get_latest_indicators(df_slice)
        recent_high = df_slice.iloc[-3]['recent_high_20'] if len(df_slice) > 2 else df_slice['high'].iloc[-1]
        recent_low = df_slice.iloc[-3]['recent_low_20'] if len(df_slice) > 2 else df_slice['low'].iloc[-1]
        
        close_p = df_slice['close'].iloc[-1]
        atr = indicators['atr']
        
        rh_dist = (recent_high - close_p) / atr if atr > 0 else 0
        rl_dist = (close_p - recent_low) / atr if atr > 0 else 0
        
        ml_features = {
            "final_score": market_score['final_score'],
            "trend_score": MultiScorer.get_trend_score(df_slice, regime),
            "breakout_score": MultiScorer.get_breakout_score(df_slice),
            "reversal_score": MultiScorer.get_reversal_score(df_slice),
            "session_score": MultiScorer.get_session_score(current_candle_time, "metal"),
            "atr": atr,
            "atr_pct": (atr / close_p * 100) if close_p > 0 else 0,
            "adx": indicators['adx'],
            "ema50_slope": indicators['ema50_slope'],
            "rsi": indicators['rsi'],
            "macd": indicators['macd'],
            "hour_utc": current_candle_time.hour,
            "is_high_volatility": 1 if regime.get('volatility_state') == "HIGH_VOLATILITY" else 0,
            "is_buy": 1 if final_dir == "BUY" else 0,
            "recent_high_20_distance": rh_dist,
            "recent_low_20_distance": rl_dist,
            "recent_high_20_distance_pct": (recent_high - close_p) / close_p * 100 if close_p > 0 else 0,
            "recent_low_20_distance_pct": (close_p - recent_low) / close_p * 100 if close_p > 0 else 0
        }
        
        ml_result = ml_predictor.predict(symbol, ml_features)
        
        prob = ml_result.get('probability', 0.0)
        if prob > 0:
            stats["ml_probs"].append(prob)
            
        if ml_result['approved'] and prob >= 0.55:
            stats["ml_pass"] += 1
            stats["simulated_orders"] += 1

    mt5_client.disconnect()
    
    print("\n--- XAUUSDm Dry Run Diagnostics Report ---")
    print(f"Candles Checked: {stats['candles_checked']}")
    print(f"Indicators Pass: {stats['indicators_pass']}")
    print(f"Regime Pass: {stats['regime_pass']}")
    print(f"Quant Pass: {stats['quant_pass']} (Bias detected)")
    print(f"ML Pass: {stats['ml_pass']} (Prob >= 0.55)")
    print(f"Simulated Orders: {stats['simulated_orders']}")
    print("------------------------------------------")
    if stats['quant_scores']:
        print(f"Quant Score Avg: {np.mean(stats['quant_scores']):.2f}")
        print(f"Quant Score Max: {np.max(stats['quant_scores']):.2f}")
        print(f"Quant Score Min: {np.min(stats['quant_scores']):.2f}")
    if stats['ml_probs']:
        print(f"ML Prob Avg: {np.mean(stats['ml_probs']):.3f}")
        print(f"ML Prob Max: {np.max(stats['ml_probs']):.3f}")
        print(f"ML Prob Min: {np.min(stats['ml_probs']):.3f}")
    else:
        print("ML Prob Avg: 0.0 (No valid signals)")

if __name__ == "__main__":
    run_diagnostics()
