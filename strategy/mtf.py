import pandas as pd
import numpy as np

class MTFContext:
    def __init__(self):
        pass

    def calculate(self, df_m5):
        """
        Since we cannot reliably fetch M15/H1 synchronously in this quick backtest script
        without refactoring mt5_client, we will simulate the H1 market structure by resynthesizing
        the M5 candles into H1 candles, and calculating the market structure on it.
        We will STRICTLY forward-fill only closed H1 candles to avoid look-ahead bias.
        """
        res = df_m5.copy()
        
        # Ensure datetime index
        if 'time' in res.columns:
            res['time'] = pd.to_datetime(res['time'])
            res.set_index('time', inplace=True)
            
        # Resample to H1
        # Label='left', closed='left' means 10:00 to 10:59 becomes the 10:00 candle
        h1_df = res.resample('1h').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'tick_volume': 'sum'
        }).dropna()
        
        # Calculate Market Structure on H1
        from strategy.market_structure import MarketStructure
        ms_h1 = MarketStructure(left_bars=2, right_bars=2)
        h1_res = ms_h1.calculate(h1_df)
        
        # Extract features we want to map back to M5
        h1_features = h1_res[['struct_trend']].copy()
        h1_features.rename(columns={'struct_trend': 'h1_struct_trend'}, inplace=True)
        
        # SHIFT H1 features by 1 to ensure we only use CLOSED H1 candles
        # e.g., the 10:00 candle closes at 10:59:59. It becomes available at 11:00.
        # So we shift the 10:00 row down to 11:00.
        h1_features_shifted = h1_features.shift(1)
        
        # Merge back to M5 using forward-fill
        # We reindex the shifted H1 features to match the M5 index
        # method='ffill' will propagate the last known closed H1 value to all M5 candles within the hour
        res = res.join(h1_features_shifted, how='left')
        res['h1_struct_trend'] = res['h1_struct_trend'].ffill()
        
        # If 'time' was a column, restore it
        if 'time' in df_m5.columns:
            res.reset_index(inplace=True)
            
        return res

mtf_context = MTFContext()
