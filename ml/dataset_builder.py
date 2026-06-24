import pandas as pd
import os
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator
from market.regime_detector import RegimeDetector
from strategy.scorer import MultiScorer
from strategy.setups import SetupEvaluator
from config.settings import settings

def build_dataset(atr_multiplier=2.0):
    import glob
    atr_str = str(atr_multiplier).replace('.', '_')
    base_file = f"ml_volatility_expansion_atr_{atr_str}"
    
    os.makedirs("datasets", exist_ok=True)
    existing = glob.glob(f"datasets/{base_file}_v*.csv")
    
    max_v = 0
    for f in existing:
        v_str = f.split("_v")[-1].replace(".csv", "")
        if v_str.isdigit():
            max_v = max(max_v, int(v_str))
    
    v_num = max_v + 1
    version_str = f"v{v_num:03d}"
    out_file = f"datasets/{base_file}_{version_str}.csv"
    
    print(f"Building Dataset Version: {version_str}")
        
    if not mt5_client.connect():
        print("Failed to connect to MT5.")
        return
        
    print(f"Fetching 200,000 candles for ATR {atr_multiplier}...")
    df = mt5_client.get_historical_data(settings.SYMBOL, settings.TIMEFRAME, 200000)
    if df is None or df.empty:
        print("No data fetched.")
        return
        
    print(f"Loaded {len(df)} candles.")
    df = IndicatorCalculator.add_indicators(df)
    
    # Target Setup parameters
    rr_ratio = 2.5
    target_setup = "Volatility Expansion Breakout"
    
    records = df.to_dict('records')
    dataset_rows = []
    
    print("Building dataset...")
    
    for i in range(200, len(records) - 100):  # leave some buffer at the end for TP/SL simulation
        df_slice = df.iloc[i-5:i+1]
        regime_slice = df.iloc[i-50:i+1]
        
        regime = RegimeDetector.detect(regime_slice)
        setups = SetupEvaluator.evaluate_all(df_slice, regime)
        
        target = None
        for s in setups:
            if s['setup_name'] == target_setup:
                target = s
                break
                
        if not target or target['direction'] == "NEUTRAL":
            continue
            
        candle = records[i]
        direction = target['direction']
        entry_price_bid = candle['close']
        spread_val = settings.BACKTEST_SPREAD_POINTS * 0.001
        
        sl_price_diff = candle['atr'] * atr_multiplier
        tp_price_diff = sl_price_diff * rr_ratio
        
        if direction == "BUY":
            entry_price = entry_price_bid + spread_val
            sl = entry_price - sl_price_diff
            tp = entry_price + tp_price_diff
        else:
            entry_price = entry_price_bid
            sl = entry_price + sl_price_diff
            tp = entry_price - tp_price_diff
            
        result_r = 0.0
        # Forward simulation
        for j in range(i+1, len(records)):
            f_candle = records[j]
            high = f_candle['high']
            low = f_candle['low']
            
            hit_sl = False
            hit_tp = False
            
            if direction == "BUY":
                if low <= sl:
                    hit_sl = True
                if high >= tp:
                    hit_tp = True
            else:
                ask_high = high + spread_val
                ask_low = low + spread_val
                if ask_high >= sl:
                    hit_sl = True
                if ask_low <= tp:
                    hit_tp = True
                    
            if hit_sl and hit_tp:
                hit_tp = False
                
            if hit_sl:
                result_r = -1.0
                break
            elif hit_tp:
                result_r = rr_ratio
                break
                
        if result_r == 0.0:
            continue
            
        # Extract features
        dt_time = pd.to_datetime(candle['time'])
        
        # Re-enable MultiScorer for feature extraction
        trend_score = MultiScorer.get_trend_score(df_slice, regime)
        breakout_score = MultiScorer.get_breakout_score(df_slice)
        reversal_score = MultiScorer.get_reversal_score(df_slice)
        session_score = MultiScorer.get_session_score(dt_time)
        
        # Distances
        recent_high = df_slice.iloc[-2]['recent_high_20'] if i > 0 else candle['high']
        recent_low = df_slice.iloc[-2]['recent_low_20'] if i > 0 else candle['low']
        
        rh_dist = (recent_high - candle['close']) / candle['atr'] if candle['atr'] > 0 else 0
        rl_dist = (candle['close'] - recent_low) / candle['atr'] if candle['atr'] > 0 else 0
        
        row = {
            "timestamp": candle['time'],
            "final_score": target['score'],
            "trend_score": trend_score,
            "breakout_score": breakout_score,
            "reversal_score": reversal_score,
            "session_score": session_score,
            "atr": candle['atr'],
            "adx": candle['adx'],
            "ema50_slope": candle['ema50_slope'],
            "rsi": candle['rsi'],
            "macd": candle['macd'],
            "trend_state": regime.get('trend_state', 'UNKNOWN'),
            "volatility_state": regime.get('volatility_state', 'UNKNOWN'),
            "direction": direction,
            "hour_utc": dt_time.hour,
            "is_high_volatility": 1 if regime.get('volatility_state') == "HIGH_VOLATILITY" else 0,
            "is_buy": 1 if direction == "BUY" else 0,
            "recent_high_20_distance": rh_dist,
            "recent_low_20_distance": rl_dist,
            "result_r": result_r,
            "label": 1 if result_r > 0 else 0
        }
        dataset_rows.append(row)
        
        if len(dataset_rows) % 100 == 0:
            print(f"Collected {len(dataset_rows)} candidates...")
            
    res_df = pd.DataFrame(dataset_rows)
    print(f"Dataset build complete! Total candidates: {len(res_df)}")
    
    os.makedirs("datasets", exist_ok=True)
    res_df.to_csv(out_file, index=False)
    print(f"Saved to {out_file}")

if __name__ == "__main__":
    import sys
    atr_mult = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    build_dataset(atr_mult)
