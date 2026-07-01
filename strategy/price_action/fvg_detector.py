import pandas as pd
import logging

logger = logging.getLogger(__name__)

class FVGDetector:
    @staticmethod
    def detect_recent_fvg(df: pd.DataFrame, lookback: int = 30) -> dict:
        """
        Detects unmitigated Fair Value Gaps (FVG) in the recent price action.
        Returns the nearest Bullish and Bearish FVGs.
        """
        if df is None or len(df) < lookback + 2:
            return {"bullish_fvg": [], "bearish_fvg": []}
            
        bullish_fvgs = []
        bearish_fvgs = []
        
        start_idx = max(2, len(df) - lookback)
        for i in range(start_idx, len(df)):
            prev_high = df['high'].iloc[i-2]
            prev_low = df['low'].iloc[i-2]
            
            curr_high = df['high'].iloc[i]
            curr_low = df['low'].iloc[i]
            
            # Bullish FVG: Candle 1 High < Candle 3 Low
            if curr_low > prev_high:
                bullish_fvgs.append({
                    "top": curr_low,
                    "bottom": prev_high
                })
                
            # Bearish FVG: Candle 1 Low > Candle 3 High
            if curr_high < prev_low:
                bearish_fvgs.append({
                    "top": prev_low,
                    "bottom": curr_high
                })
                
        current_price = df['close'].iloc[-1]
        
        valid_bullish = []
        for fvg in bullish_fvgs:
            if current_price > fvg["top"]:
                valid_bullish.append(fvg)
                
        valid_bearish = []
        for fvg in bearish_fvgs:
            if current_price < fvg["bottom"]:
                valid_bearish.append(fvg)
                
        return {
            "bullish_fvg": valid_bullish,
            "bearish_fvg": valid_bearish
        }
        
    @staticmethod
    def get_fvg_alignment(direction: str, fvgs: dict, current_price: float, atr: float = 0.0) -> bool:
        """
        Checks if there is an aligned FVG nearby to provide support/resistance.
        """
        if direction == "LONG":
            for fvg in fvgs.get("bullish_fvg", []):
                dist = current_price - fvg["top"]
                if 0 <= dist <= (atr * 4): # Within 4 ATR
                    return True
        elif direction == "SHORT":
            for fvg in fvgs.get("bearish_fvg", []):
                dist = fvg["bottom"] - current_price
                if 0 <= dist <= (atr * 4): # Within 4 ATR
                    return True
        return False
