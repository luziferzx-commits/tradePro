import pandas as pd
from .base import BaseStrategy, SignalDecision

class StrategyABreakout(BaseStrategy):
    """
    Strategy A: Breakout
    - London Breakout, NY Breakout, Volatility Expansion Breakout
    - Uses recent_high_20 / recent_low_20
    - Requires session filter, ATR expansion or ADX confirmation
    - Avoids false breakout using close confirmation
    """
    
    def generate_signal(self, df: pd.DataFrame, regime: dict) -> SignalDecision:
        if self.is_disabled_by_evidence:
            return self.get_neutral_signal(f"Disabled: {self.disabled_reason}")
            
        if df.empty or len(df) < 20:
            return self.get_neutral_signal("Insufficient data")
            
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        hour_utc = pd.to_datetime(latest['time']).hour if 'time' in latest else 0
        is_london = 7 <= hour_utc < 10
        is_ny = 13 <= hour_utc < 16
        
        # We only look for breakouts in London or NY sessions (or high vol expansion)
        is_high_volatility = regime.get('is_high_volatility', False)
        if not (is_london or is_ny or is_high_volatility):
            return self.get_neutral_signal("Not in Breakout Session/Regime")
            
        adx = latest.get('adx', 0)
        atr = latest.get('atr', 1)
        close = latest['close']
        
        dist_high_pct = latest.get('recent_high_20_distance_pct', 100)
        dist_low_pct = latest.get('recent_low_20_distance_pct', 100)
        
        # Close confirmation (must close near the high/low)
        body = abs(close - latest['open'])
        upper_wick = latest['high'] - max(close, latest['open'])
        lower_wick = min(close, latest['open']) - latest['low']
        
        # London / NY Breakout logic
        if dist_high_pct < 0.2 and close > latest['open']:
            # Check false breakout avoidance: upper wick shouldn't be massive
            if upper_wick < body * 1.5 and adx > 20:
                return SignalDecision(
                    strategy_id="StrategyABreakout",
                    setup_name="Session Breakout BUY",
                    direction="BUY",
                    confidence_score=75.0,
                    entry_reason="Near 20-period High in Breakout Session with ADX > 20",
                    stop_loss=close - (atr * 1.5),
                    take_profit=close + (atr * 2.5),
                    expected_rr=2.5/1.5,
                    invalidation_reason="",
                    required_regime="BREAKOUT",
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    timestamp=latest.get('time', 0),
                    entry_price=close
                )
                
        if dist_low_pct < 0.2 and close < latest['open']:
            if lower_wick < body * 1.5 and adx > 20:
                return SignalDecision(
                    strategy_id="StrategyABreakout",
                    setup_name="Session Breakout SELL",
                    direction="SELL",
                    confidence_score=75.0,
                    entry_reason="Near 20-period Low in Breakout Session with ADX > 20",
                    stop_loss=close + (atr * 1.5),
                    take_profit=close - (atr * 2.5),
                    expected_rr=2.5/1.5,
                    invalidation_reason="",
                    required_regime="BREAKOUT",
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    timestamp=latest.get('time', 0),
                    entry_price=close
                )
                
        return self.get_neutral_signal("No Breakout Setup Found")
