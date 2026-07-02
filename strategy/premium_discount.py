import pandas as pd
import numpy as np

class PremiumDiscount:
    def __init__(self, lookback=100):
        self.lookback = lookback

    def calculate(self, df):
        """
        Calculates Premium/Discount Zone features.
        range_position_pct: 0% is bottom of range, 100% is top of range.
        """
        res = df.copy()
        
        # Calculate recent trading range
        # Use shift(1) to avoid look-ahead if we consider the current candle part of the range
        # but typically range is calculated up to the current close
        range_high = res['high'].rolling(self.lookback).max()
        range_low = res['low'].rolling(self.lookback).min()
        
        range_size = np.maximum(range_high - range_low, 0.00001)
        
        # 0% = low, 100% = high
        res['range_position_pct'] = (res['close'] - range_low) / range_size * 100
        
        # Zones
        res['is_premium_zone'] = res['range_position_pct'] >= 75.0
        res['is_discount_zone'] = res['range_position_pct'] <= 25.0
        res['is_equilibrium_zone'] = (res['range_position_pct'] > 25.0) & (res['range_position_pct'] < 75.0)

        return res

premium_discount = PremiumDiscount(lookback=100)
