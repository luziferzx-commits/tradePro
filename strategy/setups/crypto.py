import pandas as pd
from datetime import datetime
from strategy.setups.base import BaseSetupEvaluator
from news.crypto_rss import CryptoSentimentAnalyzer

class CryptoEvaluator(BaseSetupEvaluator):
    def evaluate_all(self, df: pd.DataFrame, regime: dict, h4_trend: str = "NEUTRAL", asset_class: str = "CRYPTO") -> list:
        """
        Evaluates setups specifically tailored for Crypto (24/7).
        """
        setups = []
        if len(df) < 5:
            return setups
            
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        adx = latest.get('adx', 0)
        close = latest['close']
        high = latest['high']
        low = latest['low']
        ema50 = latest.get('ema50', 0)
        recent_high = prev.get('recent_high_20', high)
        recent_low = prev.get('recent_low_20', low)
        
        # Bolinger Bands for squeeze if available (we will approximate using ATR for now if BB not present)
        # Assuming bb_upper, bb_lower are calculated in indicators.py
        bb_upper = latest.get('bb_upper', 0)
        bb_lower = latest.get('bb_lower', 0)
        
        # Get live Sentiment (Temporarily disabled for backtest training to allow learning both directions)
        # sentiment_data = CryptoSentimentAnalyzer.get_current_sentiment()
        # sentiment = sentiment_data['sentiment']
        sentiment = "NEUTRAL"
        
        # 1. Crypto Momentum Breakout
        setups.append(self._evaluate_momentum_breakout(
            close, prev['close'], recent_high, recent_low, adx, ema50, h4_trend, sentiment
        ))
        
        # 2. Bollinger Squeeze Breakout
        setups.append(self._evaluate_bollinger_squeeze(
            close, prev['close'], bb_upper, bb_lower, adx, regime, sentiment
        ))
        
        return setups

    def _evaluate_momentum_breakout(self, close, prev_close, recent_high, recent_low, adx, ema50, h4_trend, sentiment):
        direction = "NEUTRAL"
        
        if close > recent_high and prev_close <= recent_high and close > ema50:
            direction = "BUY"
        elif close < recent_low and prev_close >= recent_low and close < ema50:
            direction = "SELL"
            
        if direction == "NEUTRAL":
            return {"setup_name": "Crypto Momentum Breakout", "direction": "NEUTRAL", "score": 0, "reason": "No momentum breakout"}
            
        # Crypto needs strong ADX to follow through
        if adx < 25:
            return {"setup_name": "Crypto Momentum Breakout", "direction": "NEUTRAL", "score": 0, "reason": "Weak ADX for Crypto"}
            
        score = 70
        if adx > 35:
            score += 10
            
        if direction == "BUY" and h4_trend == "UP":
            score += 10
        elif direction == "SELL" and h4_trend == "DOWN":
            score += 10
            
        score = min(score, 95)
        
        # Apply Macro Sentiment Filter
        if direction == "BUY" and sentiment == "BEARISH":
            return {"setup_name": "Crypto Momentum Breakout", "direction": "NEUTRAL", "score": 0, "reason": "Blocked by BEARISH Crypto News"}
        elif direction == "SELL" and sentiment == "BULLISH":
            return {"setup_name": "Crypto Momentum Breakout", "direction": "NEUTRAL", "score": 0, "reason": "Blocked by BULLISH Crypto News"}
            
        if direction == "BUY" and sentiment == "BULLISH":
            score = min(score + 15, 100)
        elif direction == "SELL" and sentiment == "BEARISH":
            score = min(score + 15, 100)
            
        return {"setup_name": "Crypto Momentum Breakout", "direction": direction, "score": score, "reason": f"Momentum score {score}"}

    def _evaluate_bollinger_squeeze(self, close, prev_close, bb_upper, bb_lower, adx, regime, sentiment):
        if bb_upper == 0 or bb_lower == 0:
            return {"setup_name": "Bollinger Squeeze", "direction": "NEUTRAL", "score": 0, "reason": "No BB data"}
            
        bb_width = (bb_upper - bb_lower) / close
        
        # Wait for a squeeze (e.g. width < 0.5% for crypto)
        if bb_width > 0.005: 
            return {"setup_name": "Bollinger Squeeze", "direction": "NEUTRAL", "score": 0, "reason": "BB not squeezing"}
            
        direction = "NEUTRAL"
        if close > bb_upper and prev_close <= bb_upper:
            direction = "BUY"
        elif close < bb_lower and prev_close >= bb_lower:
            direction = "SELL"
            
        if direction == "NEUTRAL":
            return {"setup_name": "Bollinger Squeeze", "direction": "NEUTRAL", "score": 0, "reason": "No squeeze breakout"}
            
        score = 80
        if adx > 25:
            score += 10
            
        # Apply Macro Sentiment Filter
        if direction == "BUY" and sentiment == "BEARISH":
            return {"setup_name": "Bollinger Squeeze", "direction": "NEUTRAL", "score": 0, "reason": "Blocked by BEARISH Crypto News"}
        elif direction == "SELL" and sentiment == "BULLISH":
            return {"setup_name": "Bollinger Squeeze", "direction": "NEUTRAL", "score": 0, "reason": "Blocked by BULLISH Crypto News"}
            
        if direction == "BUY" and sentiment == "BULLISH":
            score = min(score + 15, 100)
        elif direction == "SELL" and sentiment == "BEARISH":
            score = min(score + 15, 100)
            
        return {"setup_name": "Bollinger Squeeze", "direction": direction, "score": score, "reason": "BB Squeeze Explosion"}
