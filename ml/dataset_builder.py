import pandas as pd
import os
from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator
from market.regime_detector import RegimeDetector
from strategy.scorer import MultiScorer
from strategy.market_score import MarketScoreCalculator
from config.settings import settings

def build_dataset(symbol="XAUUSDm", timeframe="M5", atr_multiplier=2.0, asset_class="FOREX", max_candles=200000):
    import glob
    atr_str = str(atr_multiplier).replace('.', '_')
    base_file = f"{symbol}_dataset_atr_{atr_str}"
    
    out_dir = f"datasets/{symbol}"
    os.makedirs(out_dir, exist_ok=True)
    existing = glob.glob(f"{out_dir}/{base_file}_v*.csv")
    
    max_v = 0
    for f in existing:
        v_str = f.split("_v")[-1].replace(".csv", "")
        if v_str.isdigit():
            max_v = max(max_v, int(v_str))
    
    v_num = max_v + 1
    version_str = f"v{v_num:03d}"
    out_file = f"{out_dir}/{base_file}_{version_str}.csv"
    
    print(f"Building Dataset for {symbol} Version: {version_str} (Target Candles: {max_candles})")
        
    if not mt5_client.connect():
        print("Failed to connect to MT5.")
        return
        
    print(f"Fetching candles for {symbol} (ATR {atr_multiplier})...")
    df = mt5_client.get_historical_data(symbol, timeframe, max_candles)
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
        
        # We need h4_trend. Let's just default to NEUTRAL here to speed up backtest label generation 
        # (or ideally fetch H4 data, but for now NEUTRAL is okay for label generation focus)
        h4_trend = "NEUTRAL"
        
        score_result = MarketScoreCalculator.calculate(df_slice, regime, h4_trend=h4_trend, asset_class=asset_class)
        direction = score_result['final_direction']
        
        if direction == "NEUTRAL":
            continue
            
        target = {
            "direction": direction,
            "setup_name": score_result['setup_name']
        }
            
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
        
        # We need market_type for session score
        import yaml
        market_type = "metal"
        try:
            with open("config/symbols.yaml", "r") as f:
                sym_cfg = yaml.safe_load(f)
                market_type = sym_cfg.get(symbol, {}).get("market_type", "metal")
        except:
            pass
            
        trend_score = MultiScorer.get_trend_score(df_slice, regime)
        breakout_score = MultiScorer.get_breakout_score(df_slice)
        reversal_score = MultiScorer.get_reversal_score(df_slice)
        session_score = MultiScorer.get_session_score(dt_time, market_type)
        
        # Distances
        recent_high = df_slice.iloc[-2]['recent_high_20'] if i > 0 else candle['high']
        recent_low = df_slice.iloc[-2]['recent_low_20'] if i > 0 else candle['low']
        
        rh_dist = (recent_high - candle['close']) / candle['atr'] if candle['atr'] > 0 else 0
        rl_dist = (candle['close'] - recent_low) / candle['atr'] if candle['atr'] > 0 else 0
        
        # Normalized Features
        close_p = candle['close']
        atr_pct = (candle['atr'] / close_p) * 100 if close_p > 0 else 0
        rh_dist_pct = ((recent_high - close_p) / close_p) * 100 if close_p > 0 else 0
        rl_dist_pct = ((close_p - recent_low) / close_p) * 100 if close_p > 0 else 0
        
        row = {
            "timestamp": candle['time'],
            "final_score": score_result['final_score'],
            "trend_score": trend_score,
            "breakout_score": breakout_score,
            "reversal_score": reversal_score,
            "session_score": session_score,
            "atr": candle['atr'],
            "atr_pct": atr_pct,
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
            "recent_high_20_distance_pct": rh_dist_pct,
            "recent_low_20_distance_pct": rl_dist_pct,
            "result_r": result_r,
            "label": 1 if result_r > 0 else 0
        }
        
        # --- LAYER B: RUNTIME DATA VALIDATION ---
        # Assert no future bar access occurred in feature extraction
        assert df_slice.index[-1] == i, f"Leakage Alert! Current index is {i} but df_slice extends to {df_slice.index[-1]}"
        # Ensure timestamp alignment
        assert str(df_slice.iloc[-1]['time']) == str(candle['time']), "Leakage Alert! Timestamp mismatch between features and target candle."
        
        dataset_rows.append(row)
        
        if len(dataset_rows) % 100 == 0:
            print(f"Collected {len(dataset_rows)} candidates...")
            
    res_df = pd.DataFrame(dataset_rows)
    print(f"Dataset build complete! Total candidates: {len(res_df)}")
    
    os.makedirs(out_dir, exist_ok=True)
    res_df.to_csv(out_file, index=False)
    print(f"Saved to {out_file}")
    return out_file

if __name__ == "__main__":
    import sys
    symbol = sys.argv[1] if len(sys.argv) > 1 else "XAUUSDm"
    timeframe = sys.argv[2] if len(sys.argv) > 2 else "M5"
    atr_mult = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
    build_dataset(symbol, timeframe, atr_mult)
