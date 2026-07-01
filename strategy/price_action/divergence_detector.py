import pandas as pd


class DivergenceDetector:
    @staticmethod
    def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0.0).ewm(alpha=1 / period, adjust=False).mean()
        loss = (-delta.clip(upper=0.0)).ewm(alpha=1 / period, adjust=False).mean()
        rs = gain / loss.replace(0, 1e-12)
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def _swings(values: pd.Series, window: int, mode: str) -> list[int]:
        idxs = []
        for i in range(window, len(values) - window):
            area = values.iloc[i - window : i + window + 1]
            value = values.iloc[i]
            if mode == "high" and value == area.max():
                idxs.append(i)
            elif mode == "low" and value == area.min():
                idxs.append(i)
        return idxs

    @staticmethod
    def detect_h4_divergence(df_h4: pd.DataFrame | None, window: int = 3) -> dict:
        if df_h4 is None or len(df_h4) < 80:
            return {"type": "NONE"}

        df = df_h4.copy()
        df["rsi"] = DivergenceDetector._rsi(df["close"].astype(float))
        recent = df.tail(80).reset_index(drop=True)

        highs = DivergenceDetector._swings(recent["high"].astype(float), window, "high")
        lows = DivergenceDetector._swings(recent["low"].astype(float), window, "low")

        if len(highs) >= 2:
            a, b = highs[-2], highs[-1]
            price_higher_high = float(recent.loc[b, "high"]) > float(recent.loc[a, "high"])
            rsi_lower_high = float(recent.loc[b, "rsi"]) < float(recent.loc[a, "rsi"])
            if price_higher_high and rsi_lower_high:
                return {
                    "type": "BEARISH_DIVERGENCE",
                    "rsi_prev": float(recent.loc[a, "rsi"]),
                    "rsi_last": float(recent.loc[b, "rsi"]),
                }

        if len(lows) >= 2:
            a, b = lows[-2], lows[-1]
            price_lower_low = float(recent.loc[b, "low"]) < float(recent.loc[a, "low"])
            rsi_higher_low = float(recent.loc[b, "rsi"]) > float(recent.loc[a, "rsi"])
            if price_lower_low and rsi_higher_low:
                return {
                    "type": "BULLISH_DIVERGENCE",
                    "rsi_prev": float(recent.loc[a, "rsi"]),
                    "rsi_last": float(recent.loc[b, "rsi"]),
                }

        return {"type": "NONE"}

    @staticmethod
    def conflicts_with_direction(direction: str, divergence: dict) -> bool:
        div_type = str(divergence.get("type") or "NONE")
        if direction == "LONG" and div_type == "BEARISH_DIVERGENCE":
            return True
        if direction == "SHORT" and div_type == "BULLISH_DIVERGENCE":
            return True
        return False
