import pandas as pd
from .base import BaseStrategy, SignalDecision

class StrategyCMeanReversion(BaseStrategy):
    """
    Strategy C: Mean Reversion / Range Reversal
    - RSI exhaustion reversal, Range boundary bounce
    - Requires RANGING regime, low ADX
    - Avoids trading against strong trend
    """
    
    def generate_signal(self, df: pd.DataFrame, regime: dict) -> SignalDecision:
        if self.is_disabled_by_evidence:
            return self.get_neutral_signal(f"Disabled: {self.disabled_reason}")
            
        if df.empty or len(df) < 20:
            return self.get_neutral_signal("Insufficient data")
            
        latest = df.iloc[-1]
        
        is_ranging = regime.get('is_ranging', False)
        if not is_ranging:
            return self.get_neutral_signal("Not in Ranging Regime")
            
        adx = latest.get('adx', 50)
        atr = latest.get('atr', 2.0)
        rsi = latest.get('rsi', 50)
        close = latest['close']
        
        # We need ADX to be low for mean reversion
        if adx > 25:
            return self.get_neutral_signal("ADX too high for Mean Reversion")
            
        # Rejection wick logic
        body = abs(close - latest['open'])
        upper_wick = latest['high'] - max(close, latest['open'])
        lower_wick = min(close, latest['open']) - latest['low']
        
        # Strategy C V2 Logic (Price Action RSI Exhaustion)
        prev = df.iloc[-2]
        bullish_candle = close > latest['open']
        bearish_candle = close < latest['open']
        prev_bearish = prev['close'] < prev['open']
        prev_bullish = prev['close'] > prev['open']
        
        # Divergence / Extreme Exhaustion
        if rsi < 30 and bullish_candle and prev_bearish and lower_wick >= body * 0.5:
            return SignalDecision(
                strategy_id="StrategyCMeanReversion",
                setup_name="RSI Exhaustion BUY",
                direction="BUY",
                confidence_score=75.0,
                entry_reason="RSI Oversold, Ranging Market, Bullish Rejection",
                stop_loss=close - (atr * 1.5),
                take_profit=close + (atr * 2.0),
                expected_rr=2.0/1.5,
                invalidation_reason="",
                required_regime="RANGING",
                symbol=self.symbol,
                timeframe=self.timeframe,
                timestamp=latest.get('time', 0),
                entry_price=close
            )
            
        if rsi > 70 and bearish_candle and prev_bullish and upper_wick >= body * 0.5:
            return SignalDecision(
                strategy_id="StrategyCMeanReversion",
                setup_name="RSI Exhaustion SELL",
                direction="SELL",
                confidence_score=75.0,
                entry_reason="RSI Overbought, Ranging Market, Bearish Rejection",
                stop_loss=close + (atr * 1.5),
                take_profit=close - (atr * 2.0),
                expected_rr=2.0/1.5,
                invalidation_reason="",
                required_regime="RANGING",
                symbol=self.symbol,
                timeframe=self.timeframe,
                timestamp=latest.get('time', 0),
                entry_price=close
            )
            
        return self.get_neutral_signal("No Mean Reversion Setup Found")
