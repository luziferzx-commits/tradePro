import pandas as pd
import numpy as np

class LiquiditySweep:
    def __init__(self):
        pass

    def calculate(self, df):
        """
        Calculates 3-Layer Liquidity Sweeps and their Quality Scores.
        """
        res = df.copy()
        
        # We need datetime index or column to extract hour/day
        if 'time' in res.columns:
            time_series = pd.to_datetime(res['time'])
        else:
            time_series = res.index
            
        res['hour'] = time_series.dt.hour
        res['date'] = time_series.dt.date

        # Layer 1: Session Highs/Lows
        # Define simple session boundaries (UTC)
        # Asia: 0-8, London: 8-16, NY: 13-21
        
        # Calculate daily cumulative max/min per session
        # For simplicity in this backtest script, we compute rolling window approximations
        # Or exact group by day
        
        # Layer 2: Daily Highs/Lows
        # Shift by 1 to prevent look-ahead: we want the *previous* day's high/low
        daily_hl = res.groupby('date').agg({'high': 'max', 'low': 'min'}).shift(1)
        res = res.merge(daily_hl, on='date', how='left', suffixes=('', '_prev_day'))
        
        # Sweep Detection Logic
        # A bullish sweep (sweeping a low) occurs when Low < TargetLevel AND Close > TargetLevel
        # A bearish sweep (sweeping a high) occurs when High > TargetLevel AND Close < TargetLevel
        
        # Layer 2 Sweeps
        res['sweep_daily_high'] = (res['high'] > res['high_prev_day']) & (res['close'] < res['high_prev_day'])
        res['sweep_daily_low'] = (res['low'] < res['low_prev_day']) & (res['close'] > res['low_prev_day'])
        
        # Quality Scores for Daily Sweeps
        # wick_ratio: how much of the sweep candle is a wick? (High - max(O,C)) / (High - Low)
        candle_range = np.maximum(res['high'] - res['low'], 0.00001)
        res['bearish_wick_ratio'] = (res['high'] - np.maximum(res['open'], res['close'])) / candle_range
        res['bullish_wick_ratio'] = (np.minimum(res['open'], res['close']) - res['low']) / candle_range
        
        # rejection_distance: how far did it close below/above the level?
        res['rejection_dist_daily_high'] = np.where(res['sweep_daily_high'], res['high_prev_day'] - res['close'], 0.0)
        res['rejection_dist_daily_low'] = np.where(res['sweep_daily_low'], res['close'] - res['low_prev_day'], 0.0)
        
        # Sweep Strength = Wick Ratio * Rejection Distance (simplified quality score)
        res['sweep_strength_daily_high'] = res['bearish_wick_ratio'] * res['rejection_dist_daily_high']
        res['sweep_strength_daily_low'] = res['bullish_wick_ratio'] * res['rejection_dist_daily_low']

        # Layer 3: Swing Highs/Lows (e.g. 50-candle swing)
        # We can calculate a 50-candle rolling max/min (excluding the current candle)
        res['swing_high_50'] = res['high'].shift(1).rolling(50).max()
        res['swing_low_50'] = res['low'].shift(1).rolling(50).min()
        
        res['sweep_swing_high_50'] = (res['high'] > res['swing_high_50']) & (res['close'] < res['swing_high_50'])
        res['sweep_swing_low_50'] = (res['low'] < res['swing_low_50']) & (res['close'] > res['swing_low_50'])
        
        # Drop temporary columns
        res.drop(columns=['hour', 'date'], inplace=True, errors='ignore')

        return res

liquidity_sweep = LiquiditySweep()
