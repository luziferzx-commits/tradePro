"""ml/feature_validator.py — Validates and sanitizes ML feature dicts."""
import math
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Per-feature clamp bounds.  key -> (min_val, max_val)
_CLAMP_RULES: dict[str, tuple[float, float]] = {
    "rsi":                      (0.0,    100.0),
    "adx":                      (0.0,    100.0),
    "final_score":              (-100.0, 100.0),
    "trend_score":              (-100.0, 100.0),
    "breakout_score":           (-100.0, 100.0),
    "reversal_score":           (-100.0, 100.0),
    "session_score":            (-100.0, 100.0),
    "recent_high_20_distance":  (-10.0,  10.0),
    "recent_low_20_distance":   (-10.0,  10.0),
    "hour_utc":                 (0.0,    23.0),
    "is_buy":                   (0.0,    1.0),
    "is_high_volatility":       (0.0,    1.0),
}

REQUIRED_FEATURE_KEYS: list[str] = [
    "final_score", "trend_score", "breakout_score", "reversal_score",
    "session_score", "atr", "adx", "ema50_slope", "rsi", "macd",
    "hour_utc", "is_high_volatility", "is_buy",
    "recent_high_20_distance", "recent_low_20_distance",
]


class FeatureValidator:

    @staticmethod
    def validate_and_sanitize(
        features: dict[str, Any]
    ) -> tuple[dict[str, Any], list[str]]:
        """
        Sanitize an ML feature dict:
        1. Replace NaN / Inf / -Inf with 0.0
        2. Apply per-key clamp rules

        Returns:
            (sanitized_dict, list_of_warning_strings)
        """
        sanitized: dict[str, Any] = {}
        warnings: list[str] = []

        for key, val in features.items():
            # --- NaN / Inf check ---
            try:
                f_val = float(val)
            except (TypeError, ValueError):
                sanitized[key] = val   # non-numeric (e.g., timestamp) — leave as-is
                continue

            if math.isnan(f_val) or math.isinf(f_val):
                warnings.append(f"{key}={f_val} → replaced with 0.0")
                f_val = 0.0

            # --- clamp ---
            if key in _CLAMP_RULES:
                lo, hi = _CLAMP_RULES[key]
                clamped = max(lo, min(hi, f_val))
                if clamped != f_val:
                    warnings.append(f"{key}={f_val} clamped to [{lo}, {hi}] → {clamped}")
                f_val = clamped

            sanitized[key] = f_val

        return sanitized, warnings

    @staticmethod
    def check_completeness(
        features: dict,
        required_keys: list[str] | None = None,
    ) -> tuple[bool, list[str]]:
        """
        Returns (True, []) if all required keys are present.
        Returns (False, [missing_keys]) otherwise.
        """
        if required_keys is None:
            required_keys = REQUIRED_FEATURE_KEYS
        missing = [k for k in required_keys if k not in features]
        if missing:
            logger.warning(f"FeatureValidator: missing keys: {missing}")
            return False, missing
        return True, []
