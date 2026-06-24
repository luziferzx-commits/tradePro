"""tests/test_feature_validator.py — Unit tests for FeatureValidator."""
import pytest
import math
from datetime import datetime
from ml.feature_validator import FeatureValidator, REQUIRED_FEATURE_KEYS


def get_base_features() -> dict:
    """Helper to return a valid feature dict."""
    return {k: 50.0 for k in REQUIRED_FEATURE_KEYS}


# ── TEST CASES FOR validate_and_sanitize ─────────────────────────────────────

def test_clean_features():
    """1. all valid values, expect no warnings, values unchanged."""
    feats = {"rsi": 50.0, "adx": 30.0, "final_score": 10.0}
    sanitized, warnings = FeatureValidator.validate_and_sanitize(feats)
    assert not warnings
    assert sanitized == feats


def test_nan_value():
    """2. one feature is float('nan'), expect replaced with 0.0, warning returned."""
    feats = {"macd": float('nan'), "rsi": 50.0}
    sanitized, warnings = FeatureValidator.validate_and_sanitize(feats)
    assert sanitized["macd"] == 0.0
    assert sanitized["rsi"] == 50.0
    assert any("replaced with 0.0" in w for w in warnings)


def test_inf_value():
    """3. one feature is float('inf'), expect replaced with 0.0."""
    feats = {"ema50_slope": float('inf')}
    sanitized, warnings = FeatureValidator.validate_and_sanitize(feats)
    assert sanitized["ema50_slope"] == 0.0
    assert any("replaced with 0.0" in w for w in warnings)


def test_neg_inf_value():
    """4. float('-inf'), expect 0.0."""
    feats = {"ema50_slope": float('-inf')}
    sanitized, warnings = FeatureValidator.validate_and_sanitize(feats)
    assert sanitized["ema50_slope"] == 0.0


def test_rsi_over_100():
    """5. rsi=150.0, expect clamped to 100.0, warning returned."""
    feats = {"rsi": 150.0}
    sanitized, warnings = FeatureValidator.validate_and_sanitize(feats)
    assert sanitized["rsi"] == 100.0
    assert any("clamped" in w for w in warnings)


def test_rsi_negative():
    """6. rsi=-5.0, expect clamped to 0.0."""
    feats = {"rsi": -5.0}
    sanitized, warnings = FeatureValidator.validate_and_sanitize(feats)
    assert sanitized["rsi"] == 0.0


def test_adx_over_100():
    """7. adx=120.0, expect clamped to 100.0."""
    feats = {"adx": 120.0}
    sanitized, warnings = FeatureValidator.validate_and_sanitize(feats)
    assert sanitized["adx"] == 100.0


def test_memory_sim_over_1():
    """
    8. a memory_sim-like field > 1.0, expect clamped.
    Note: Using is_high_volatility as a stand-in for a [0, 1] clamped field 
    since memory_sim was clamped in main.py, not inside FeatureValidator.
    """
    feats = {"is_high_volatility": 1.5}
    sanitized, warnings = FeatureValidator.validate_and_sanitize(feats)
    assert sanitized["is_high_volatility"] == 1.0


def test_mixed_bad_features():
    """9. 3 features are NaN/Inf/out-of-range simultaneously, all fixed."""
    feats = {
        "rsi": 150.0,          # clamp to 100
        "macd": float('nan'),  # fix to 0.0
        "adx": -10.0           # clamp to 0.0
    }
    sanitized, warnings = FeatureValidator.validate_and_sanitize(feats)
    assert sanitized["rsi"] == 100.0
    assert sanitized["macd"] == 0.0
    assert sanitized["adx"] == 0.0
    assert len(warnings) == 3


def test_non_numeric_key():
    """10. features include a timestamp (datetime), expect left untouched."""
    now = datetime.now()
    feats = {"timestamp": now, "rsi": 50.0}
    sanitized, warnings = FeatureValidator.validate_and_sanitize(feats)
    assert sanitized["timestamp"] == now
    assert sanitized["rsi"] == 50.0


# ── TEST CASES FOR check_completeness ────────────────────────────────────────

def test_all_keys_present():
    """11. full valid feature dict, expect (True, [])."""
    feats = get_base_features()
    ok, missing = FeatureValidator.check_completeness(feats)
    assert ok is True
    assert not missing


def test_one_key_missing():
    """12. remove 'rsi', expect (False, ['rsi'])."""
    feats = get_base_features()
    del feats["rsi"]
    ok, missing = FeatureValidator.check_completeness(feats)
    assert ok is False
    assert missing == ["rsi"]


def test_multiple_missing():
    """13. remove 3 keys, expect (False, [those 3 keys])."""
    feats = get_base_features()
    del feats["rsi"]
    del feats["adx"]
    del feats["is_buy"]
    ok, missing = FeatureValidator.check_completeness(feats)
    assert ok is False
    assert set(missing) == {"rsi", "adx", "is_buy"}


def test_empty_dict():
    """14. {}, expect (False, all required keys listed)."""
    ok, missing = FeatureValidator.check_completeness({})
    assert ok is False
    assert set(missing) == set(REQUIRED_FEATURE_KEYS)
