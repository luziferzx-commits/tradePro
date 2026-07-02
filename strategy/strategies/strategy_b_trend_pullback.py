import pandas as pd
from .base import BaseStrategy, SignalDecision

class StrategyBTrendPullback(BaseStrategy):
    """
    Strategy B: Trend Pullback
    - EMA50 pullback continuation
    - Requires TRENDING_UP or TRENDING_DOWN, ADX threshold
    - Requires EMA slope confirmation
    """
    
    def generate_signal(self, df: pd.DataFrame, regime: dict) -> SignalDecision:
        if self.is_disabled_by_evidence:
            return self.get_neutral_signal(f"Disabled: {self.disabled_reason}")
            
        if df.empty or len(df) < 50:
            return self.get_neutral_signal("Insufficient data")
            
        latest = df.iloc[-1]
        
        is_trending_up = regime.get('is_trending_up', False)
        is_trending_down = regime.get('is_trending_down', False)
        
        if not (is_trending_up or is_trending_down):
            return self.get_neutral_signal("Not in Trending Regime")
            
        adx = latest.get('adx', 0)
        atr = latest.get('atr', 1.0)
        close = latest['close']
        ema50 = latest.get('ema50', close)
        ema50_slope = latest.get('ema50_slope', 0)
        
        if adx < 25:
            return self.get_neutral_signal("ADX too low for Trend Pullback")
            
        dist_to_ema = (close - ema50) / atr
        
        # BUY Setup: Pullback to EMA in an uptrend
        if is_trending_up and ema50_slope > 0.5:
            if 0 < dist_to_ema < 1.0: # Pullback near EMA
                # Wait for bullish candle to resume trend
                if close > latest['open']:
                    return SignalDecision(
                        strategy_id="StrategyBTrendPullback",
                        setup_name="EMA Pullback BUY",
                        direction="BUY",
                        confidence_score=80.0,
                        entry_reason="Pullback to EMA50 in Uptrend, Bullish Rejection",
                        stop_loss=close - (atr * 1.5),
                        take_profit=close + (atr * 3.0),
                        expected_rr=3.0/1.5,
                        invalidation_reason="",
                        required_regime="TRENDING_UP",
                        symbol=self.symbol,
                        timeframe=self.timeframe,
                        timestamp=latest.get('time', 0),
                        entry_price=close
                    )
                    
        # SELL Setup: Pullback to EMA in a downtrend
        if is_trending_down and ema50_slope < -0.5:
            if -1.0 < dist_to_ema < 0:
                if close < latest['open']:
                    return SignalDecision(
                        strategy_id="StrategyBTrendPullback",
                        setup_name="EMA Pullback SELL",
                        direction="SELL",
                        confidence_score=80.0,
                        entry_reason="Pullback to EMA50 in Downtrend, Bearish Rejection",
                        stop_loss=close + (atr * 1.5),
                        take_profit=close - (atr * 3.0),
                        expected_rr=3.0/1.5,
                        invalidation_reason="",
                        required_regime="TRENDING_DOWN",
                        symbol=self.symbol,
                        timeframe=self.timeframe,
                        timestamp=latest.get('time', 0),
                        entry_price=close
                    )
                    
        return self.get_neutral_signal("No Pullback Setup Found")
