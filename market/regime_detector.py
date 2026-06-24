import pandas as pd

class RegimeDetector:
    @staticmethod
    def detect(df: pd.DataFrame) -> dict:
        """
        Analyzes the DataFrame to determine market regime (trend & volatility)
        Expects df with EMA50, EMA200, ATR, ADX, plus_di, minus_di, and ema50_slope calculated.
        """
        # Require fewer columns now to avoid early unknown, but handle gracefully
        if len(df) < 50 or 'ema50' not in df.columns or 'adx' not in df.columns:
            return {"trend_state": "UNKNOWN", "volatility_state": "UNKNOWN"}

        current = df.iloc[-1]
        
        # Volatility Detection using ATR vs historical average ATR
        avg_atr = df['atr'].rolling(window=50).mean().iloc[-1] if 'atr' in df.columns else 0
        volatility_state = "NORMAL_VOLATILITY"
        if pd.notna(avg_atr) and avg_atr > 0:
            if current['atr'] > avg_atr * 1.5:
                volatility_state = "HIGH_VOLATILITY"
            elif current['atr'] < avg_atr * 0.5:
                volatility_state = "LOW_VOLATILITY"

        # Trend Detection using ADX and EMA Slope
        trend_state = "RANGING"
        adx = current.get('adx', 0)
        plus_di = current.get('plus_di', 0)
        minus_di = current.get('minus_di', 0)
        ema_slope = current.get('ema50_slope', 0)
        
        is_trending = adx > 25
        
        if is_trending:
            if plus_di > minus_di and ema_slope > 0.5:
                trend_state = "TRENDING_UP"
            elif minus_di > plus_di and ema_slope < -0.5:
                trend_state = "TRENDING_DOWN"
        else:
            trend_state = "RANGING"

        return {
            "trend_state": trend_state,
            "volatility_state": volatility_state
        }
