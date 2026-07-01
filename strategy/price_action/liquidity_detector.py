import pandas as pd


class LiquidityDetector:
    @staticmethod
    def previous_daily_levels(df_d1: pd.DataFrame | None) -> dict:
        if df_d1 is None or len(df_d1) < 2:
            return {"pdh": None, "pdl": None}
        prev = df_d1.iloc[-1]
        return {"pdh": float(prev["high"]), "pdl": float(prev["low"])}

    @staticmethod
    def detect_pdh_pdl_sweep(latest, levels: dict, buffer_atr: float = 0.0) -> dict:
        pdh = levels.get("pdh")
        pdl = levels.get("pdl")
        if pdh is None or pdl is None:
            return {"type": "NONE", "pdh": pdh, "pdl": pdl}

        high = float(latest["high"])
        low = float(latest["low"])
        close = float(latest["close"])
        buffer = max(float(buffer_atr or 0.0) * 0.05, 0.0)

        if high > pdh + buffer and close < pdh:
            return {"type": "BEARISH_SWEEP_PDH", "level": pdh, "pdh": pdh, "pdl": pdl}
        if low < pdl - buffer and close > pdl:
            return {"type": "BULLISH_SWEEP_PDL", "level": pdl, "pdh": pdh, "pdl": pdl}
        return {"type": "NONE", "pdh": pdh, "pdl": pdl}

    @staticmethod
    def conflicts_with_direction(direction: str, sweep: dict) -> bool:
        sweep_type = str(sweep.get("type") or "NONE")
        if direction == "LONG" and sweep_type == "BEARISH_SWEEP_PDH":
            return True
        if direction == "SHORT" and sweep_type == "BULLISH_SWEEP_PDL":
            return True
        return False
