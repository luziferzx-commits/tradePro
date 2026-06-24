import pandas as pd
from strategy.base import BaseStrategy

class PrimarySignalGenerator(BaseStrategy):
    def __init__(self):
        super().__init__("Primary_Trend_Strategy")

    def generate_signal(self, df: pd.DataFrame, regime: dict) -> str:
        if len(df) < 2:
            return "NEUTRAL"
            
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        trend = regime.get('trend_state')
        
        # Rule-based logic
        if trend == "TRENDING_UP":
            # Buy signal: Price above EMA50, MACD crossover, RSI not overbought
            if (current['macd'] > current['macd_signal'] and previous['macd'] <= previous['macd_signal']) and \
               current['rsi'] < 70:
                return "BUY"
                
        elif trend == "TRENDING_DOWN":
            # Sell signal: Price below EMA50, MACD crossunder, RSI not oversold
            if (current['macd'] < current['macd_signal'] and previous['macd'] >= previous['macd_signal']) and \
               current['rsi'] > 30:
                return "SELL"
                
        return "NEUTRAL"
