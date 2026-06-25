import pandas as pd
from datetime import datetime
from strategy.setups.base import BaseSetupEvaluator
from news.market_rss import MarketSentimentAnalyzer

class ForexMetalsEvaluator(BaseSetupEvaluator):
    def evaluate_all(self, df: pd.DataFrame, regime: dict, h4_trend: str = "NEUTRAL", asset_class: str = "FOREX") -> list:
        """
        Evaluates all setups and returns a list of diagnostic dictionaries.
        """
        setups = []
        if len(df) < 5:
            return setups
            
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        dt_time = pd.to_datetime(latest['time'])
        hour = dt_time.hour
        
        adx = latest.get('adx', 0)
        atr = latest.get('atr', 0)
        close = latest['close']
        open_price = latest['open']
        high = latest['high']
        low = latest['low']
        ema50 = latest.get('ema50', 0)
        plus_di = latest.get('plus_di', 0)
        minus_di = latest.get('minus_di', 0)
        recent_high = prev.get('recent_high_20', high)
        recent_low = prev.get('recent_low_20', low)
        
        # Get macro sentiment (Temporarily disabled during backtest by hardcoding to NEUTRAL)
        # sentiment_data = MarketSentimentAnalyzer.get_current_sentiment(asset_class)
        # sentiment = sentiment_data['sentiment']
        sentiment = "NEUTRAL"
        
        # 1. London Breakout
        setups.append(self._evaluate_breakout(
            "London Breakout", hour in [7, 8, 9, 10], open_price, close, prev['close'], 
            recent_high, recent_low, adx, atr, high, low, h4_trend, regime, sentiment
        ))
        
        # 2. NY Breakout
        setups.append(self._evaluate_breakout(
            "NY Breakout", hour in [13, 14, 15, 16], open_price, close, prev['close'], 
            recent_high, recent_low, adx, atr, high, low, h4_trend, regime, sentiment
        ))
        
        # 3. RSI Exhaustion Reversal
        setups.append(self._evaluate_rsi_reversal(
            df, close, ema50, prev['close'], prev.get('ema50', 0)
        ))
        
        # 4. Volatility Expansion Breakout
        setups.append(self._evaluate_volatility_expansion(
            adx, plus_di, minus_di, close, prev['close'], recent_high, recent_low, regime
        ))
        
        # 5. Asia Session Continuation (DISABLED - Needs rigorous backtesting on n>200 historical samples first)
        # setups.append(self._evaluate_asia_continuation(
        #     "Asia Continuation", hour in [17, 18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4], 
        #     close, ema50, regime.get('trend_state', 'UNKNOWN'), rsi=latest.get('rsi', 50)
        # ))
        
        return setups

    
    def _evaluate_breakout(self, name, time_cond, open_price, close, prev_close, recent_high, recent_low, adx, atr, high, low, h4_trend, regime, sentiment="NEUTRAL"):
        trend_state = regime.get('trend_state', 'UNKNOWN')
        if trend_state == "RANGING":
            return {
                "setup_name": name, "direction": "NEUTRAL", "score": 0,
                "reason": "Blocked: Ranging market (breakout failure risk)",
                "failed_conditions": ["Trending Regime Required"]
            }

        if not time_cond:
            return {"setup_name": name, "direction": "NEUTRAL", "score": 0, "reason": "Not in session"}
            
        direction = "NEUTRAL"
        if close > recent_high and prev_close <= recent_high:
            direction = "BUY"
        elif close < recent_low and prev_close >= recent_low:
            direction = "SELL"
            
        if direction == "NEUTRAL":
            return {"setup_name": name, "direction": "NEUTRAL", "score": 0, "reason": "No breakout detected"}
            
        score = 65
        if adx > 25:
            score += 10
            
        candle_range = high - low
        body_size = abs(close - open_price)
        if candle_range > 0 and body_size > (candle_range * 0.5):
            score += 10
            
        if direction == "BUY":
            if atr > 0 and (close - recent_high) > (0.1 * atr):
                score += 10
            if h4_trend == "UP":
                score += 10
            elif h4_trend == "DOWN":
                score -= 20
        else:
            if atr > 0 and (recent_low - close) > (0.1 * atr):
                score += 10
            if h4_trend == "DOWN":
                score += 10
            elif h4_trend == "UP":
                score -= 20
                
        score = min(max(score, 0), 95)
        
        # Apply Macro Sentiment
        if direction == "BUY" and sentiment == "BEARISH":
            score -= 10
        elif direction == "SELL" and sentiment == "BULLISH":
            score -= 10
        
        if direction == "BUY" and sentiment == "BULLISH":
            score = min(score + 10, 100)
        elif direction == "SELL" and sentiment == "BEARISH":
            score = min(score + 10, 100)
            
        score = max(score, 0)
        if score < 50:
            return {"setup_name": name, "direction": "NEUTRAL", "score": 0, "reason": "Blocked by low score after sentiment penalty"}
            
        return {"setup_name": name, "direction": direction, "score": score, "reason": f"Breakout score {score}"}

    
    def _evaluate_rsi_reversal(self, df_slice, close, ema50, prev_close, prev_ema50):
        recent = df_slice.iloc[-5:]
        min_rsi = recent['rsi'].min()
        max_rsi = recent['rsi'].max()
        current_rsi = recent['rsi'].iloc[-1]
        
        if min_rsi < 30 and current_rsi > 35 and close > ema50 and prev_close <= prev_ema50:
            return {"setup_name": "RSI Exhaustion Reversal", "direction": "BUY", "score": 75, "reason": "Oversold recovery"}
        elif max_rsi > 70 and current_rsi < 65 and close < ema50 and prev_close >= prev_ema50:
            return {"setup_name": "RSI Exhaustion Reversal", "direction": "SELL", "score": 75, "reason": "Overbought rollover"}
            
        return {"setup_name": "RSI Exhaustion Reversal", "direction": "NEUTRAL", "score": 0, "reason": "No reversal"}

    
    def _evaluate_volatility_expansion(self, adx, plus_di, minus_di, close, prev_close, recent_high, recent_low, regime):
        trend_state = regime.get('trend_state', 'UNKNOWN')
        if trend_state == "RANGING":
            return {
                "setup_name": "Volatility Expansion Breakout", "direction": "NEUTRAL", "score": 0,
                "reason": "Blocked: Ranging market (breakout failure risk)",
                "failed_conditions": ["Trending Regime Required"]
            }

        if adx < 30:
            return {"setup_name": "Volatility Expansion Breakout", "direction": "NEUTRAL", "score": 0, "reason": "ADX < 30"}
            
        direction = "NEUTRAL"
        if plus_di > minus_di and close > recent_high and prev_close <= recent_high:
            direction = "BUY"
        elif minus_di > plus_di and close < recent_low and prev_close >= recent_low:
            direction = "SELL"
            
        if direction == "NEUTRAL":
            return {"setup_name": "Volatility Expansion Breakout", "direction": "NEUTRAL", "score": 0, "reason": "No expansion breakout"}
            
        score = 65
        if adx > 35:
            score += 10
        if direction == "BUY" and (plus_di - minus_di) > 5:
            score += 10
        elif direction == "SELL" and (minus_di - plus_di) > 5:
            score += 10
            
        score = min(score, 85)
        return {"setup_name": "Volatility Expansion Breakout", "direction": direction, "score": score, "reason": f"Expansion score {score}"}

    def _evaluate_asia_continuation(self, name, time_cond, close, ema50, trend_state, rsi):
        if not time_cond:
            return {"setup_name": name, "direction": "NEUTRAL", "score": 0, "reason": "Not in session"}
            
        if trend_state == "RANGING":
            return {"setup_name": name, "direction": "NEUTRAL", "score": 0, "reason": "Market is ranging"}
            
        direction = "NEUTRAL"
        if trend_state == "TRENDING_UP" and close > ema50 and rsi < 70:
            direction = "BUY"
        elif trend_state == "TRENDING_DOWN" and close < ema50 and rsi > 30:
            direction = "SELL"
            
        if direction == "NEUTRAL":
            return {"setup_name": name, "direction": "NEUTRAL", "score": 0, "reason": "No continuation setup"}
            
        return {"setup_name": name, "direction": direction, "score": 65, "reason": "Asia Session Continuation matched"}
