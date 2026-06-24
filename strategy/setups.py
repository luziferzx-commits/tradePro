import pandas as pd
from datetime import datetime

class SetupEvaluator:
    @staticmethod
    def evaluate_all(df: pd.DataFrame, regime: dict) -> list:
        """
        Evaluates all setups and returns a list of diagnostic dictionaries.
        """
        setups = []
        if len(df) < 2:
            return setups
            
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        dt_time = pd.to_datetime(latest['time'])
        hour = dt_time.hour
        
        adx = latest['adx']
        rsi = latest['rsi']
        close = latest['close']
        high = latest['high']
        low = latest['low']
        ema50 = latest['ema50']
        recent_high = prev['recent_high_20']
        recent_low = prev['recent_low_20']
        trend_state = regime.get('trend_state', 'UNKNOWN')
        
        # 1. London Breakout
        setups.append(SetupEvaluator._evaluate_breakout(
            "London Breakout", hour in [7, 8, 9, 10], close, prev['close'], recent_high, recent_low
        ))
        
        # 2. NY Breakout
        setups.append(SetupEvaluator._evaluate_breakout(
            "NY Breakout", hour in [13, 14, 15, 16], close, prev['close'], recent_high, recent_low
        ))
        
        # 3. EMA Pullback Continuation
        setups.append(SetupEvaluator._evaluate_ema_pullback(
            adx, trend_state, close, high, low, ema50, prev['close'], prev['ema50']
        ))
        
        # 4. RSI Exhaustion Reversal
        setups.append(SetupEvaluator._evaluate_rsi_reversal(
            df, close, ema50, prev['close'], prev['ema50']
        ))
        
        # 5. Range Boundary Bounce
        setups.append(SetupEvaluator._evaluate_range_bounce(
            trend_state, close, high, low, recent_high, recent_low
        ))
        
        # 6. Volatility Expansion Breakout
        setups.append(SetupEvaluator._evaluate_volatility_expansion(
            adx, latest['plus_di'], latest['minus_di'], close, prev['close'], recent_high, recent_low
        ))
        
        return setups

    @staticmethod
    def _evaluate_breakout(name, time_cond, close, prev_close, recent_high, recent_low):
        if not time_cond:
            return {"setup_name": name, "direction": "NEUTRAL", "score": 0, "reason": "Not in session", "failed_conditions": ["Session Time"]}
            
        if close > recent_high and prev_close <= recent_high:
            return {"setup_name": name, "direction": "BUY", "score": 85, "reason": "Broke 20-period high", "failed_conditions": []}
        elif close < recent_low and prev_close >= recent_low:
            return {"setup_name": name, "direction": "SELL", "score": 85, "reason": "Broke 20-period low", "failed_conditions": []}
            
        return {"setup_name": name, "direction": "NEUTRAL", "score": 0, "reason": "No breakout detected", "failed_conditions": ["Price inside range"]}

    @staticmethod
    def _evaluate_ema_pullback(adx, trend_state, close, high, low, ema50, prev_close, prev_ema50):
        if adx < 25:
            return {"setup_name": "EMA Pullback Continuation", "direction": "NEUTRAL", "score": 0, "reason": "ADX < 25 (Weak trend)", "failed_conditions": ["ADX > 25"]}
            
        if trend_state == "TRENDING_UP":
            if low <= ema50 and close > ema50: # Touched but rejected
                return {"setup_name": "EMA Pullback Continuation", "direction": "BUY", "score": 80, "reason": "Bounce off EMA50 in Uptrend", "failed_conditions": []}
        elif trend_state == "TRENDING_DOWN":
            if high >= ema50 and close < ema50:
                return {"setup_name": "EMA Pullback Continuation", "direction": "SELL", "score": 80, "reason": "Rejection at EMA50 in Downtrend", "failed_conditions": []}
                
        return {"setup_name": "EMA Pullback Continuation", "direction": "NEUTRAL", "score": 0, "reason": "No pullback rejection", "failed_conditions": ["EMA Bounce"]}

    @staticmethod
    def _evaluate_rsi_reversal(df_slice, close, ema50, prev_close, prev_ema50):
        min_rsi = df_slice['rsi'].min()
        max_rsi = df_slice['rsi'].max()
        
        if min_rsi < 30 and close > ema50 and prev_close <= prev_ema50:
            return {"setup_name": "RSI Exhaustion Reversal", "direction": "BUY", "score": 80, "reason": "Oversold RSI + Structural Break UP", "failed_conditions": []}
        elif max_rsi > 70 and close < ema50 and prev_close >= prev_ema50:
            return {"setup_name": "RSI Exhaustion Reversal", "direction": "SELL", "score": 80, "reason": "Overbought RSI + Structural Break DOWN", "failed_conditions": []}
            
        return {"setup_name": "RSI Exhaustion Reversal", "direction": "NEUTRAL", "score": 0, "reason": "No exhaustion reversal", "failed_conditions": ["RSI Extreme", "EMA Cross"]}

    @staticmethod
    def _evaluate_range_bounce(trend_state, close, high, low, recent_high, recent_low):
        if trend_state != "RANGING":
            return {"setup_name": "Range Boundary Bounce", "direction": "NEUTRAL", "score": 0, "reason": "Not in ranging market", "failed_conditions": ["Ranging Regime"]}
            
        range_size = recent_high - recent_low
        if range_size == 0:
            return {"setup_name": "Range Boundary Bounce", "direction": "NEUTRAL", "score": 0, "reason": "Zero range", "failed_conditions": ["Valid Range"]}
            
        # Bounce off bottom
        if low <= recent_low + (range_size * 0.1) and close > low:
            return {"setup_name": "Range Boundary Bounce", "direction": "BUY", "score": 75, "reason": "Bounce off range support", "failed_conditions": []}
        # Bounce off top
        if high >= recent_high - (range_size * 0.1) and close < high:
            return {"setup_name": "Range Boundary Bounce", "direction": "SELL", "score": 75, "reason": "Rejection at range resistance", "failed_conditions": []}
            
        return {"setup_name": "Range Boundary Bounce", "direction": "NEUTRAL", "score": 0, "reason": "Middle of range", "failed_conditions": ["Boundary Touch"]}

    @staticmethod
    def _evaluate_volatility_expansion(adx, plus_di, minus_di, close, prev_close, recent_high, recent_low):
        if adx < 30:
            return {"setup_name": "Volatility Expansion Breakout", "direction": "NEUTRAL", "score": 0, "reason": "ADX < 30", "failed_conditions": ["High ADX"]}
            
        if plus_di > minus_di and close > recent_high and prev_close <= recent_high:
            return {"setup_name": "Volatility Expansion Breakout", "direction": "BUY", "score": 85, "reason": "Bullish expansion breakout", "failed_conditions": []}
        elif minus_di > plus_di and close < recent_low and prev_close >= recent_low:
            return {"setup_name": "Volatility Expansion Breakout", "direction": "SELL", "score": 85, "reason": "Bearish expansion breakout", "failed_conditions": []}
            
        return {"setup_name": "Volatility Expansion Breakout", "direction": "NEUTRAL", "score": 0, "reason": "No expansion breakout", "failed_conditions": ["Breakout"]}
