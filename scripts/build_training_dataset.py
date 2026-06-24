"""scripts/build_training_dataset.py — Fetch historical MT5 data and build a labeled dataset for XGBoost."""
import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime

# Add root directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.settings import settings
from data.mt5_client import mt5_client
import MetaTrader5 as mt5

# Import feature and strategy components
from strategy.indicators import IndicatorCalculator
from market.regime_detector import RegimeDetector
from strategy.market_score import MarketScoreCalculator

from risk.sl_tp_calculator import SLTPCalculator
from ml.feature_validator import REQUIRED_FEATURE_KEYS

logger = logging.getLogger("DatasetBuilder")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def simulate_trade_outcome(df: pd.DataFrame, current_idx: int, direction: str, sl_points: int, tp_points: int, max_holding_candles: int = 50) -> int:
    """
    Simulates if a trade hits TP (1) or SL/timeout (0) looking forward up to max_holding_candles.
    Returns 1 for win, 0 for loss.
    """
    entry_price = df['close'].iloc[current_idx]
    sl_dist = sl_points * 0.01
    tp_dist = tp_points * 0.01
    
    if direction == "BUY":
        tp_price = entry_price + tp_dist
        sl_price = entry_price - sl_dist
    else:  # SELL
        tp_price = entry_price - tp_dist
        sl_price = entry_price + sl_dist

    # Look forward up to 50 candles
    forward_slice = df.iloc[current_idx + 1 : current_idx + 1 + max_holding_candles]
    
    for _, row in forward_slice.iterrows():
        high = row['high']
        low = row['low']
        
        if direction == "BUY":
            # Check SL first within the candle to be pessimistic (conservative)
            if low <= sl_price:
                return 0
            if high >= tp_price:
                return 1
        else: # SELL
            if high >= sl_price:
                return 0
            if low <= tp_price:
                return 1
                
    # Timeout
    return 0


def build_dataset(num_candles: int = 15000):
    logger.info("Initializing MT5 connection...")
    if not mt5_client.connect():
        logger.error("Failed to connect to MT5.")
        return

    symbol = settings.SYMBOL
    
    # Map timeframe string to MT5 constant (e.g. "M5" -> mt5.TIMEFRAME_M5)
    tf_map = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1
    }
    timeframe = tf_map.get(settings.TIMEFRAME, mt5.TIMEFRAME_M5)

    logger.info(f"Fetching {num_candles} historical candles for {symbol}...")
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_candles)
    if rates is None or len(rates) == 0:
        logger.error("Failed to fetch rates from MT5.")
        mt5_client.disconnect()
        return

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Required columns for MT5 data: time, open, high, low, close, tick_volume, spread, real_volume
    # 3. Add indicators
    logger.info("Calculating technical indicators...")
    df = IndicatorCalculator.add_indicators(df)
    
    logger.info("Fetching H4 data for trend filter...")
    df_h4 = mt5_client.get_h4_data(symbol, num_candles // 48 + 50)
    if df_h4 is not None and not df_h4.empty:
        df_h4['h4_ema50'] = df_h4['close'].ewm(span=50).mean()
        df_h4['h4_trend'] = np.where(df_h4['close'] > df_h4['h4_ema50'], 'UP', 'DOWN')
        df_h4_clean = df_h4[['time', 'h4_trend']].rename(columns={'time': 'h4_time'})
        df = pd.merge_asof(df.sort_values('time'), df_h4_clean.sort_values('h4_time'), left_on='time', right_on='h4_time', direction='backward')
        df['h4_trend'] = df['h4_trend'].fillna('NEUTRAL')
    else:
        df['h4_trend'] = 'NEUTRAL'
    
    dataset_rows = []
    
    logger.info("Starting row-by-row simulation and label generation...")
    
    # We need a rolling window for realistic evaluation. 
    # Start loop from index 100 to allow indicators (like EMA50, RSI) to warm up
    start_idx = 100
    
    for i in range(start_idx, len(df)):
        if i % 500 == 0:
            logger.info(f"Processed {i}/{len(df)} candles...")
            
        row = df.iloc[i]
        
        # Skip if ATR is 0 or NaN
        if 'atr' not in df.columns or pd.isna(row['atr']) or row['atr'] <= 0:
            continue
            
        # Extract df_slice up to current candle to avoid lookahead bias
        df_slice = df.iloc[:i+1]
        
        # 4. Regime Detection
        regime = RegimeDetector.detect(df_slice)
        
        # 5. Market Score Calculation
        h4_trend = row.get('h4_trend', 'NEUTRAL')
        score_result = MarketScoreCalculator.calculate(df_slice, regime, h4_trend=h4_trend)
        direction = score_result.get('final_direction', 'NEUTRAL')
        
        if direction == 'NEUTRAL':
            continue
            
        from strategy.scorer import MultiScorer
        
        # Calculate recent highs and lows using the slice
        recent_high = df_slice['high'].rolling(20).max().iloc[-3] if len(df_slice) > 2 else df_slice['high'].iloc[-1]
        recent_low = df_slice['low'].rolling(20).min().iloc[-3] if len(df_slice) > 2 else df_slice['low'].iloc[-1]
        rh_dist = (recent_high - row['close']) / row['atr'] if row['atr'] > 0 else 0
        rl_dist = (row['close'] - recent_low) / row['atr'] if row['atr'] > 0 else 0
        
        features = {
            "final_score": score_result['final_score'],
            "trend_score": MultiScorer.get_trend_score(df_slice, regime),
            "breakout_score": MultiScorer.get_breakout_score(df_slice),
            "reversal_score": MultiScorer.get_reversal_score(df_slice),
            "session_score": MultiScorer.get_session_score(row['time'], "metal"),
            "atr": row['atr'],
            "adx": row.get('adx', 0.0),
            "ema50_slope": row.get('ema50_slope', 0.0),
            "rsi": row.get('rsi', 0.0),
            "macd": row.get('macd', 0.0),
            "hour_utc": row['time'].hour,
            "is_high_volatility": 1 if regime.get('volatility_state') == "HIGH_VOLATILITY" else 0,
            "is_buy": 1 if direction == "BUY" else 0,
            "recent_high_20_distance": rh_dist,
            "recent_low_20_distance": rl_dist,
        }
        
        # Ensure all required features are present
        missing = [k for k in REQUIRED_FEATURE_KEYS if k not in features]
        if missing:
            logger.warning(f"Missing keys: {missing}")
            continue # Skip if feature extractor failed to provide required keys
            
        # 6. Label Generation (Simulate forward)
        # Use SLTPCalculator to get realistic dynamic SL
        sl_tp = SLTPCalculator.calculate(df_slice, direction, rr_ratio=2.0)
        sl_points = sl_tp['sl_points']
        tp_points = sl_tp['tp_points']
        
        label = simulate_trade_outcome(
            df=df,
            current_idx=i,
            direction=direction,
            sl_points=sl_points,
            tp_points=tp_points,
            max_holding_candles=50
        )
        
        # Record data row
        data_row = {
            'timestamp': row['time'],
            'direction': direction,
            'label': label
        }
        
        # Add required features
        for key in REQUIRED_FEATURE_KEYS:
            data_row[key] = features.get(key, 0.0)
            
        dataset_rows.append(data_row)
        
    mt5_client.disconnect()
    
    if not dataset_rows:
        logger.warning("No valid signals generated. Dataset is empty.")
        return
        
    # Create final DataFrame
    out_df = pd.DataFrame(dataset_rows)
    
    # Save to disk
    os.makedirs("datasets", exist_ok=True)
    today_str = datetime.now().strftime("%Y%m%d")
    out_file = f"datasets/training_data_{today_str}.csv"
    out_df.to_csv(out_file, index=False)
    
    logger.info(f"Dataset successfully saved to {out_file}")
    
    # Print class balance
    n_total = len(out_df)
    n_win = len(out_df[out_df['label'] == 1])
    n_loss = n_total - n_win
    win_rate = (n_win / n_total) * 100 if n_total > 0 else 0.0
    
    print("\n" + "="*40)
    print(" DATASET GENERATION SUMMARY ")
    print("="*40)
    print(f"Total Samples : {n_total}")
    print(f"Wins (Label 1): {n_win}")
    print(f"Loss (Label 0): {n_loss}")
    print(f"Win Rate      : {win_rate:.2f}%")
    print("="*40)

if __name__ == "__main__":
    build_dataset(num_candles=15000)
