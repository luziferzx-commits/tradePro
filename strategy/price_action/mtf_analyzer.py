import pandas as pd
import logging

logger = logging.getLogger(__name__)

class MTFAnalyzer:
    @staticmethod
    def evaluate_trend(df: pd.DataFrame) -> str:
        """
        Evaluates the major trend of a higher timeframe dataframe using EMA50 and EMA200.
        Returns "BULLISH", "BEARISH", or "NEUTRAL".
        """
        if df is None or len(df) < 200:
            return "UNKNOWN"
            
        try:
            # We just need EMA50 and EMA200
            ema50 = df['close'].ewm(span=50, adjust=False).mean()
            ema200 = df['close'].ewm(span=200, adjust=False).mean()
            
            curr_ema50 = ema50.iloc[-1]
            curr_ema200 = ema200.iloc[-1]
            
            # Simple trend identification
            if curr_ema50 > curr_ema200:
                return "BULLISH"
            elif curr_ema50 < curr_ema200:
                return "BEARISH"
            else:
                return "NEUTRAL"
        except Exception as e:
            logger.warning(f"Error calculating MTF trend: {e}")
            return "UNKNOWN"
