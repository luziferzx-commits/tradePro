from datetime import datetime, timezone
from typing import Any

import pandas as pd


class InstitutionalFilters:
    @staticmethod
    def choppiness_index(df: pd.DataFrame | None, period: int = 14) -> float | None:
        if df is None or len(df) < period + 2:
            return None
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)
        prev_close = close.shift(1)
        tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        atr_sum = tr.tail(period).sum()
        high_low_range = high.tail(period).max() - low.tail(period).min()
        if high_low_range <= 0:
            return None
        import math
        return float(100.0 * math.log10(atr_sum / high_low_range) / math.log10(period))

    @staticmethod
    def dry_breakout(df: pd.DataFrame | None, lookback: int = 20) -> dict:
        if df is None or len(df) < lookback + 2 or "tick_volume" not in df.columns:
            return {"is_dry_breakout": False}
        last = df.iloc[-1]
        prev = df.iloc[-lookback - 1 : -1]
        candle_range = float(last["high"] - last["low"])
        avg_range = float((prev["high"] - prev["low"]).mean())
        volume = float(last["tick_volume"])
        avg_volume = float(prev["tick_volume"].mean())
        if avg_range <= 0 or avg_volume <= 0:
            return {"is_dry_breakout": False}
        is_range_break = candle_range >= avg_range * 1.35
        is_volume_dry = volume <= avg_volume * 0.80
        return {
            "is_dry_breakout": bool(is_range_break and is_volume_dry),
            "volume_ratio": volume / avg_volume,
            "range_ratio": candle_range / avg_range,
        }

    @staticmethod
    def killzone_label(ts: Any = None) -> str:
        if ts is None:
            dt = datetime.now(timezone.utc)
        elif isinstance(ts, datetime):
            dt = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(timezone.utc)
        else:
            try:
                dt = pd.Timestamp(ts).to_pydatetime()
                dt = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                dt = dt.astimezone(timezone.utc)
            except Exception:
                dt = datetime.now(timezone.utc)
        hour = dt.hour + (dt.minute / 60.0)
        if 7.0 <= hour < 10.0:
            return "LONDON_OPEN"
        if 12.5 <= hour < 16.0:
            return "NY_OPEN"
        if 0.0 <= hour < 5.0:
            return "ASIA"
        if 20.0 <= hour or hour < 0.5:
            return "ROLLOVER"
        return "OFF_KILLZONE"

    @staticmethod
    def trend_following_allowed(killzone: str) -> bool:
        return killzone in {"LONDON_OPEN", "NY_OPEN"}

    @staticmethod
    def usd_direction_for_symbol(symbol: str, direction: str) -> int:
        clean = str(symbol or "").upper().replace("M", "")
        direction = str(direction or "").upper()
        if clean in {"XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD"}:
            return -1 if direction == "LONG" else 1
        if clean.endswith("USD") and not clean.startswith("USD"):
            return -1 if direction == "LONG" else 1
        if clean.startswith("USD"):
            return 1 if direction == "LONG" else -1
        return 0

    @staticmethod
    def usd_basket_trend(mt5_client) -> dict:
        pairs = [
            ("EURUSD", -1.0),
            ("GBPUSD", -1.0),
            ("AUDUSD", -1.0),
            ("NZDUSD", -1.0),
            ("USDCAD", 1.0),
            ("USDJPY", 1.0),
        ]
        scores = []
        for symbol, sign in pairs:
            try:
                df = mt5_client.get_historical_data(symbol, "H1", 40)
                if df is None or len(df) < 20:
                    continue
                close = df["close"].astype(float)
                ret = (close.iloc[-1] / close.iloc[-20]) - 1.0
                scores.append(ret * sign)
            except Exception:
                continue
        if not scores:
            return {"trend": "UNKNOWN", "score": 0.0}
        score = sum(scores) / len(scores)
        if score > 0.0015:
            trend = "USD_BULLISH"
        elif score < -0.0015:
            trend = "USD_BEARISH"
        else:
            trend = "USD_NEUTRAL"
        return {"trend": trend, "score": float(score), "samples": len(scores)}

    @staticmethod
    def usd_conflicts(symbol: str, direction: str, usd_context: dict) -> bool:
        exposure = InstitutionalFilters.usd_direction_for_symbol(symbol, direction)
        trend = str(usd_context.get("trend") or "UNKNOWN")
        if exposure == 0 or trend == "UNKNOWN" or trend == "USD_NEUTRAL":
            return False
        if exposure < 0 and trend == "USD_BULLISH":
            return True
        if exposure > 0 and trend == "USD_BEARISH":
            return True
        return False
