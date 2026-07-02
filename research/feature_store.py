import pandas as pd
import numpy as np
import os

class FeatureStore:
    @staticmethod
    def extract_features(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        
        if len(df) < 200:
            return df
            
        # Ensure base indicators are present
        required = ['ema50', 'rsi', 'atr', 'adx', 'ema50_slope']
        for col in required:
            if col not in df.columns:
                return df

        # RSI Bucket
        bins_rsi = [-1, 30, 70, 101]
        labels_rsi = ['Oversold (<30)', 'Neutral (30-70)', 'Overbought (>70)']
        df['rsi_bucket'] = pd.cut(df['rsi'], bins=bins_rsi, labels=labels_rsi)
        
        # Price Position relative to EMA50 (normalized by ATR)
        dist_ema50 = (df['close'] - df['ema50']) / df['atr'].replace(0, np.nan)
        bins_pos = [-np.inf, -2, 0, 2, np.inf]
        labels_pos = ['Far Below (<-2)', 'Below (-2-0)', 'Above (0-2)', 'Far Above (>2)']
        df['price_position_bucket'] = pd.cut(dist_ema50, bins=bins_pos, labels=labels_pos)
        
        # Candle Body Bucket (normalized by ATR)
        body_size = abs(df['close'] - df['open']) / df['atr'].replace(0, np.nan)
        bins_body = [-np.inf, 0.2, 0.8, np.inf]
        labels_body = ['Doji (<0.2)', 'Normal (0.2-0.8)', 'Marubozu (>0.8)']
        df['candle_body_bucket'] = pd.cut(body_size, bins=bins_body, labels=labels_body)
        
        # Wick Rejection
        upper_wick = df['high'] - df[['open', 'close']].max(axis=1)
        lower_wick = df[['open', 'close']].min(axis=1) - df['low']
        
        def get_wick_rejection(row):
            bs = abs(row['close'] - row['open'])
            if row['upper_wick'] > 2 * bs and row['upper_wick'] > row['lower_wick']:
                return "Bearish Pinbar"
            elif row['lower_wick'] > 2 * bs and row['lower_wick'] > row['upper_wick']:
                return "Bullish Pinbar"
            return "Balanced"
            
        temp_df = pd.DataFrame({'close': df['close'], 'open': df['open'], 'upper_wick': upper_wick, 'lower_wick': lower_wick})
        df['wick_rejection_bucket'] = temp_df.apply(get_wick_rejection, axis=1)

        # ATR Bucket (rolling 1000-candle relative ATR if possible, else global)
        df['atr_bucket'] = pd.qcut(df['atr'], 4, labels=['Low', 'Medium', 'High', 'Extreme'], duplicates='drop')

        # ADX Bucket
        bins_adx = [-1, 20, 25, 40, 100]
        labels_adx = ['Weak (<20)', 'Rising (20-25)', 'Strong (25-40)', 'Extreme (>40)']
        df['adx_bucket'] = pd.cut(df['adx'], bins=bins_adx, labels=labels_adx)
        
        # Trend Bucket (EMA50 Slope)
        tbins = [-999, -1, -0.2, 0.2, 1, 999]
        tlabels = ['Strong Down', 'Down', 'Flat', 'Up', 'Strong Up']
        df['trend_bucket'] = pd.cut(df['ema50_slope'], bins=tbins, labels=tlabels)
        
        return df
