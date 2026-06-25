import pandas as pd
import numpy as np
import os
import hashlib

class UniversalFeatureStore:
    @staticmethod
    def generate_uuid(row):
        s = f"{row['symbol']}_{row['timeframe']}_{row['entry_time_utc']}"
        return hashlib.md5(s.encode('utf-8')).hexdigest()

    @staticmethod
    def extract_features(df: pd.DataFrame, symbol: str, timeframe: str) -> pd.DataFrame:
        df = df.copy()
        
        if len(df) < 200:
            return df
            
        required = ['ema20', 'ema50', 'ema200', 'rsi', 'atr', 'adx', 'ema20_slope', 'ema50_slope', 'ema200_slope', 'recent_high_distance', 'recent_low_distance']
        for col in required:
            if col not in df.columns:
                return pd.DataFrame()

        # Add base fields
        df['symbol'] = symbol
        df['timeframe'] = timeframe
        df['entry_time_utc'] = df['time'].dt.strftime('%Y-%m-%d %H:%M:%S')
        df['year'] = df['time'].dt.year
        df['month'] = df['time'].dt.month
        df['weekday'] = df['time'].dt.weekday
        df['hour'] = df['time'].dt.hour
        
        # UUID
        df['feature_uuid'] = df.apply(UniversalFeatureStore.generate_uuid, axis=1)

        # RSI Bucket
        bins_rsi = [-1, 30, 70, 101]
        labels_rsi = ['Oversold (<30)', 'Neutral (30-70)', 'Overbought (>70)']
        df['rsi_bucket'] = pd.cut(df['rsi'], bins=bins_rsi, labels=labels_rsi).astype(str)
        
        # Price Position relative to EMA50 (normalized by ATR)
        dist_ema50 = (df['close'] - df['ema50']) / df['atr'].replace(0, np.nan)
        bins_pos = [-np.inf, -2, 0, 2, np.inf]
        labels_pos = ['Far Below (<-2)', 'Below (-2-0)', 'Above (0-2)', 'Far Above (>2)']
        df['price_position_bucket'] = pd.cut(dist_ema50, bins=bins_pos, labels=labels_pos).astype(str)
        
        # Candle Body Bucket (normalized by ATR)
        body_size = abs(df['close'] - df['open']) / df['atr'].replace(0, np.nan)
        bins_body = [-np.inf, 0.2, 0.8, np.inf]
        labels_body = ['Doji (<0.2)', 'Normal (0.2-0.8)', 'Marubozu (>0.8)']
        df['candle_body_bucket'] = pd.cut(body_size, bins=bins_body, labels=labels_body).astype(str)
        
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
        df['wick_rejection_bucket'] = temp_df.apply(get_wick_rejection, axis=1).astype(str)

        # ATR & Volatility Buckets
        atr_b = pd.qcut(df['atr'], 4, labels=['Low', 'Medium', 'High', 'Extreme'], duplicates='drop')
        df['atr_bucket'] = atr_b.astype(str)
        df['volatility_bucket'] = atr_b.astype(str) # Alias as requested

        # ADX Bucket
        bins_adx = [-1, 20, 25, 40, 100]
        labels_adx = ['Weak (<20)', 'Rising (20-25)', 'Strong (25-40)', 'Extreme (>40)']
        df['adx_bucket'] = pd.cut(df['adx'], bins=bins_adx, labels=labels_adx).astype(str)
        
        # Trend Bucket
        tbins = [-999, -1, -0.2, 0.2, 1, 999]
        tlabels = ['Strong Down', 'Down', 'Flat', 'Up', 'Strong Up']
        df['trend_bucket'] = pd.cut(df['ema50_slope'], bins=tbins, labels=tlabels).astype(str)
        
        # Spread estimate (mock dynamic for now if not available)
        if 'spread' not in df.columns:
            df['spread_estimate'] = df['atr'] * 0.05
        else:
            df['spread_estimate'] = df['spread']
            
        return df

    @staticmethod
    def save_partitioned(df: pd.DataFrame, base_dir: str):
        if df.empty: return
        store_path = os.path.join(base_dir, 'data', 'feature_store')
        os.makedirs(store_path, exist_ok=True)
        # Partition by symbol and year
        for (sym, yr), group in df.groupby(['symbol', 'year']):
            part_dir = os.path.join(store_path, f"symbol={sym}", f"year={yr}")
            os.makedirs(part_dir, exist_ok=True)
            file_path = os.path.join(part_dir, "universal_features.parquet")
            
            # Keep required columns only
            cols = [
                'feature_uuid', 'symbol', 'timeframe', 'entry_time_utc', 'year', 'month', 
                'weekday', 'hour', 'session_label', 'regime', 'atr', 'atr_bucket', 'adx', 'adx_bucket', 
                'rsi', 'rsi_bucket', 'ema20', 'ema50', 'ema200', 'ema20_slope', 'ema50_slope', 
                'ema200_slope', 'trend_bucket', 'volatility_bucket', 'spread_estimate', 
                'candle_body_bucket', 'wick_rejection_bucket', 'price_position_bucket', 
                'recent_high_distance', 'recent_low_distance'
            ]
            
            if os.path.exists(file_path):
                existing_df = pd.read_parquet(file_path)
                combined = pd.concat([existing_df, group[cols]]).drop_duplicates(subset=['feature_uuid'])
                combined.to_parquet(file_path, index=False)
            else:
                group[cols].to_parquet(file_path, index=False)
