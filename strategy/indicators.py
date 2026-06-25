import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator, ADXIndicator
from ta.volatility import AverageTrueRange, BollingerBands

class IndicatorCalculator:
    @staticmethod
    def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
        if len(df) < 200:
            return df
            
        # RSI
        rsi = RSIIndicator(close=df['close'], window=14)
        df['rsi'] = rsi.rsi()
        
        # MACD
        macd = MACD(close=df['close'], window_slow=26, window_fast=12, window_sign=9)
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_hist'] = macd.macd_diff()
        
        # EMAs
        ema50 = EMAIndicator(close=df['close'], window=50)
        df['ema50'] = ema50.ema_indicator()
        
        ema200 = EMAIndicator(close=df['close'], window=200)
        df['ema200'] = ema200.ema_indicator()
        
        # ATR
        atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14)
        df['atr'] = atr.average_true_range()

        # ADX
        adx_ind = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14)
        df['adx'] = adx_ind.adx()
        df['plus_di'] = adx_ind.adx_pos()
        df['minus_di'] = adx_ind.adx_neg()

        # Bollinger Bands
        indicator_bb = BollingerBands(close=df['close'], window=20, window_dev=2)
        df['bb_upper'] = indicator_bb.bollinger_hband()
        df['bb_lower'] = indicator_bb.bollinger_lband()

        # EMA Slope (normalized per ATR over 5 candles to make it scale-independent)
        df['ema50_slope'] = (df['ema50'].diff(5) / df['atr']) * 10

        # Structural Extremes (20-period for breakout detection)
        df['recent_high_20'] = df['high'].rolling(20).max()
        df['recent_low_20'] = df['low'].rolling(20).min()
        
        return df

    @staticmethod
    def get_latest_indicators(df: pd.DataFrame) -> dict:
        if df.empty or 'rsi' not in df.columns:
            return {}
        latest = df.iloc[-1]
        
        # Safely convert NaN to None or 0 to prevent JSON issues
        def safe_val(val):
            return 0.0 if pd.isna(val) else float(val)

        return {
            'rsi': safe_val(latest['rsi']),
            'macd': safe_val(latest['macd']),
            'macd_signal': safe_val(latest['macd_signal']),
            'macd_hist': safe_val(latest['macd_hist']),
            'ema50': safe_val(latest['ema50']),
            'ema200': safe_val(latest['ema200']),
            'atr': safe_val(latest['atr']),
            'adx': safe_val(latest['adx']),
            'plus_di': safe_val(latest['plus_di']),
            'minus_di': safe_val(latest['minus_di']),
            'ema50_slope': safe_val(latest['ema50_slope']),
            'recent_high_20': safe_val(latest['recent_high_20']),
            'recent_low_20': safe_val(latest['recent_low_20']),
            'bb_upper': safe_val(latest.get('bb_upper', 0)),
            'bb_lower': safe_val(latest.get('bb_lower', 0))
        }
