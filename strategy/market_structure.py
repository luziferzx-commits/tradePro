import pandas as pd
import numpy as np

class MarketStructure:
    def __init__(self, left_bars=5, right_bars=5):
        self.left_bars = left_bars
        self.right_bars = right_bars

    def calculate(self, df):
        """
        Calculates market structure points and trends.
        Returns a new DataFrame with structure features.
        """
        # Ensure we don't modify original dataframe
        res = df.copy()
        
        res['is_swing_high'] = False
        res['is_swing_low'] = False
        
        # Identify swing points
        for i in range(self.left_bars, len(res) - self.right_bars):
            # Swing High
            if res['high'].iloc[i] == res['high'].iloc[i-self.left_bars:i+self.right_bars+1].max():
                res.iloc[i, res.columns.get_loc('is_swing_high')] = True
                
            # Swing Low
            if res['low'].iloc[i] == res['low'].iloc[i-self.left_bars:i+self.right_bars+1].min():
                res.iloc[i, res.columns.get_loc('is_swing_low')] = True

        # Forward fill the last known swing high/low prices
        res['last_swing_high'] = np.where(res['is_swing_high'], res['high'], np.nan)
        res['last_swing_low'] = np.where(res['is_swing_low'], res['low'], np.nan)
        
        res['last_swing_high'] = res['last_swing_high'].ffill()
        res['last_swing_low'] = res['last_swing_low'].ffill()
        
        # We also want to know the *previous* swing high to determine HH vs LH
        # So we shift the forward filled series when a new swing high occurs
        
        # Extract just the swing highs
        sh_df = res[res['is_swing_high']].copy()
        sh_df['prev_swing_high'] = sh_df['high'].shift(1)
        res['prev_swing_high'] = np.nan
        res.loc[sh_df.index, 'prev_swing_high'] = sh_df['prev_swing_high']
        res['prev_swing_high'] = res['prev_swing_high'].ffill()
        
        # Extract just the swing lows
        sl_df = res[res['is_swing_low']].copy()
        sl_df['prev_swing_low'] = sl_df['low'].shift(1)
        res['prev_swing_low'] = np.nan
        res.loc[sl_df.index, 'prev_swing_low'] = sl_df['prev_swing_low']
        res['prev_swing_low'] = res['prev_swing_low'].ffill()

        # Classify the latest structure (HH, LH, HL, LL)
        # Note: These values update at the exact bar the swing is CONFIRMED (which is i + right_bars)
        # To avoid look-ahead bias, we must shift the "is_swing" signals forward by right_bars to know exactly 
        # WHEN the bot would realize it's a swing.
        
        # For simplicity in features, we just care about the state of the *known* swings
        # at any given time. The known swing high at time t is the one confirmed at t-right_bars.
        
        # Let's create shifted versions to represent "what we know right now"
        # Since we use right_bars to confirm, at time T, we only know about swings that happened at T - right_bars or earlier.
        res['known_last_swing_high'] = res['last_swing_high'].shift(self.right_bars).ffill()
        res['known_prev_swing_high'] = res['prev_swing_high'].shift(self.right_bars).ffill()
        
        res['known_last_swing_low'] = res['last_swing_low'].shift(self.right_bars).ffill()
        res['known_prev_swing_low'] = res['prev_swing_low'].shift(self.right_bars).ffill()

        # Structure State
        res['struct_hh'] = res['known_last_swing_high'] > res['known_prev_swing_high']
        res['struct_lh'] = res['known_last_swing_high'] < res['known_prev_swing_high']
        res['struct_hl'] = res['known_last_swing_low'] > res['known_prev_swing_low']
        res['struct_ll'] = res['known_last_swing_low'] < res['known_prev_swing_low']

        def get_trend(row):
            if row['struct_hh'] and row['struct_hl']:
                return "UPTREND"
            elif row['struct_lh'] and row['struct_ll']:
                return "DOWNTREND"
            else:
                return "CHOPPY"
                
        res['struct_trend'] = res.apply(get_trend, axis=1)
        
        # 1. Structural Strength
        # E.g., distance between HH and previous High, or LL and previous Low (normalized by price)
        # If uptrend: (HH - prevH) / prevH * 100
        # If downtrend: (prevL - LL) / prevL * 100
        # If choppy: 0
        def get_struct_strength(row):
            if row['struct_trend'] == "UPTREND" and row['known_prev_swing_high'] > 0:
                return (row['known_last_swing_high'] - row['known_prev_swing_high']) / row['known_prev_swing_high'] * 100
            elif row['struct_trend'] == "DOWNTREND" and row['known_last_swing_low'] > 0:
                return (row['known_prev_swing_low'] - row['known_last_swing_low']) / row['known_prev_swing_low'] * 100
            return 0.0
            
        res['struct_strength'] = res.apply(get_struct_strength, axis=1)

        # 2. Distance to last HH / LL (normalized by close price)
        res['distance_to_last_HH'] = np.where(res['known_last_swing_high'] > 0, (res['known_last_swing_high'] - res['close']) / res['close'] * 100, 0.0)
        res['distance_to_last_LL'] = np.where(res['known_last_swing_low'] > 0, (res['close'] - res['known_last_swing_low']) / res['close'] * 100, 0.0)

        # 3. Distance to breakout level
        # In an uptrend, breakout level is prev_swing_high. Distance from close to it.
        # In a downtrend, breakout level is prev_swing_low. Distance from close to it.
        def get_dist_to_breakout(row):
            if row['struct_trend'] == "UPTREND" and row['known_prev_swing_high'] > 0:
                return (row['close'] - row['known_prev_swing_high']) / row['close'] * 100
            elif row['struct_trend'] == "DOWNTREND" and row['known_prev_swing_low'] > 0:
                return (row['known_prev_swing_low'] - row['close']) / row['close'] * 100
            return 0.0
            
        res['distance_to_breakout_level'] = res.apply(get_dist_to_breakout, axis=1)

        # Output the required feature columns
        return res

market_structure = MarketStructure(left_bars=5, right_bars=5)
