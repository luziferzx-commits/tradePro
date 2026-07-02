"""risk/sl_tp_calculator.py — ATR-based dynamic SL/TP for XAUUSD."""
import logging
import math
import pandas as pd

logger = logging.getLogger(__name__)

POINT_SIZE    = 0.01   # XAUUSD: 1 point = $0.01 price movement
MIN_SL_POINTS = 150    # Hard floor  — protects vs micro-ATR data errors
MAX_SL_POINTS = 2000   # Hard ceiling— protects vs ATR spike data errors
FALLBACK_ATR  = 20.0   # Fallback ATR in price units if NaN/zero ($20)


class SLTPCalculator:

    @staticmethod
    def calculate(
        df: pd.DataFrame,
        direction: str,
        atr_multiplier_sl: float = 1.8,
        rr_ratio: float = 2.0,
    ) -> dict:
        """
        Calculate dynamic SL and TP in MT5 points.

        Args:
            df:               OHLCV + indicator DataFrame, must have 'atr' column
            direction:        'BUY' or 'SELL'
            atr_multiplier_sl: SL = atr * multiplier (default 1.8x ATR)
            rr_ratio:         TP = SL * rr_ratio (default 2.0R)

        Returns:
            {
                "sl_points": int,    # Stop Loss in MT5 points
                "tp_points": int,    # Take Profit in MT5 points
                "atr_used":  float,  # ATR value used (price units, e.g. 18.50)
                "atr_regime": str,   # 'LOW' | 'NORMAL' | 'HIGH'
                "rr_ratio":  float,
            }
        """
        # --- get ATR ---
        atr = float(df['atr'].iloc[-1]) if 'atr' in df.columns else float('nan')
        if math.isnan(atr) or atr <= 0:
            logger.warning(
                f"ATR is {atr} — using fallback ATR={FALLBACK_ATR}. "
                "Check IndicatorCalculator output."
            )
            atr = FALLBACK_ATR

        # --- SL calculation ---
        sl_price  = atr * atr_multiplier_sl
        sl_points = int(round(sl_price / POINT_SIZE))
        sl_points = max(MIN_SL_POINTS, min(MAX_SL_POINTS, sl_points))   # clamp

        # --- TP calculation ---
        tp_points = int(round(sl_points * rr_ratio))

        regime = SLTPCalculator.get_atr_regime(atr)
        logger.debug(
            f"SLTPCalculator: dir={direction} atr={atr:.2f}$ [{regime}] "
            f"sl={sl_points}pts tp={tp_points}pts RR={rr_ratio}"
        )

        return {
            "sl_points":  sl_points,
            "tp_points":  tp_points,
            "atr_used":   atr,
            "atr_regime": regime,
            "rr_ratio":   rr_ratio,
        }

    @staticmethod
    def get_atr_regime(atr_price: float) -> str:
        """Classify ATR for XAUUSD. atr_price in $ per oz."""
        if atr_price < 10.0:
            return "LOW"
        elif atr_price <= 30.0:
            return "NORMAL"
        else:
            return "HIGH"
