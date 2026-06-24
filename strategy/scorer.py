import pandas as pd
from datetime import datetime

class MultiScorer:
    @staticmethod
    def get_trend_score(df: pd.DataFrame, regime: dict) -> float:
        """ Returns [-100, 100]. Positive = Buy Bias, Negative = Sell Bias """
        if len(df) < 5: return 0.0
        current = df.iloc[-1]
        
        score = 0.0
        trend_state = regime.get('trend_state', 'RANGING')
        
        if trend_state == "TRENDING_UP":
            score += 50
            if current['macd'] > current['macd_signal']: score += 25
            if current.get('ema50_slope', 0) > 0.5: score += 25
        elif trend_state == "TRENDING_DOWN":
            score -= 50
            if current['macd'] < current['macd_signal']: score -= 25
            if current.get('ema50_slope', 0) < -0.5: score -= 25
            
        return max(-100.0, min(100.0, score))

    @staticmethod
    def get_breakout_score(df: pd.DataFrame) -> float:
        if len(df) < 20: return 0.0
        current = df.iloc[-1]
        previous_high = df.iloc[-2]['recent_high_20'] if 'recent_high_20' in df.columns else current['high']
        previous_low = df.iloc[-2]['recent_low_20'] if 'recent_low_20' in df.columns else current['low']
        
        if current['close'] > previous_high:
            return 80.0
        elif current['close'] < previous_low:
            return -80.0
        return 0.0

    @staticmethod
    def get_pullback_score(df: pd.DataFrame, regime: dict) -> float:
        if len(df) < 5: return 0.0
        current = df.iloc[-1]
        trend_state = regime.get('trend_state', 'RANGING')
        
        if trend_state == "TRENDING_UP" and current['low'] <= current['ema50'] and current['close'] > current['ema50']:
            return 75.0
        elif trend_state == "TRENDING_DOWN" and current['high'] >= current['ema50'] and current['close'] < current['ema50']:
            return -75.0
        return 0.0

    @staticmethod
    def get_reversal_score(df: pd.DataFrame) -> float:
        if len(df) < 5: return 0.0
        current = df.iloc[-1]
        rsi = current.get('rsi', 50)
        
        if rsi < 30: # Oversold -> Buy bias
            return (30 - rsi) * 5  # scales up
        elif rsi > 70: # Overbought -> Sell bias
            return (70 - rsi) * 5  # scales down
        return 0.0

    @staticmethod
    def get_session_score(current_time: datetime) -> float:
        """ Higher absolute score means better liquidity. [0, 100] """
        if not isinstance(current_time, datetime):
            return 50.0
        hour = current_time.hour
        # London/NY Overlap: 13-16 UTC
        if 13 <= hour <= 16:
            return 100.0
        elif 7 <= hour <= 22:
            return 60.0
        return 20.0
