"""tests/test_smoke.py — Smoke tests to ensure new modules import and run without crashes."""
import pytest
import pandas as pd

# ── 1. IMPORT CHECKS ─────────────────────────────────────────────────────────

def test_import_sltp_calculator():
    from risk.sl_tp_calculator import SLTPCalculator
    assert SLTPCalculator is not None

def test_import_daily_drawdown_guard():
    from risk.daily_drawdown_guard import DailyDrawdownGuard
    assert DailyDrawdownGuard is not None

def test_import_feature_validator():
    from ml.feature_validator import FeatureValidator
    assert FeatureValidator is not None

def test_import_gemini_filter_stub():
    from ai.gemini_filter import GeminiFilter
    assert GeminiFilter is not None


# ── 2. GEMINI FILTER STUB BEHAVIOR ───────────────────────────────────────────

def test_gemini_filter_stub_behavior():
    from ai.gemini_filter import GeminiFilter
    gf = GeminiFilter()
    assert gf.filter() is True
    
    result = gf.analyze()
    assert isinstance(result, dict)
    assert "approved" in result
    assert result["approved"] is True


# ── 3. SLTP CALCULATOR BASIC RUN ─────────────────────────────────────────────

def test_sltp_calculator_basic_run():
    from risk.sl_tp_calculator import SLTPCalculator
    df = pd.DataFrame({"atr": [15.0]})
    result = SLTPCalculator.calculate(df, "BUY")
    
    expected_keys = {"sl_points", "tp_points", "atr_used", "atr_regime", "rr_ratio"}
    assert set(result.keys()) == expected_keys
    assert isinstance(result["sl_points"], int)
    assert result["sl_points"] > 0


# ── 4. FEATURE VALIDATOR BASIC RUN ───────────────────────────────────────────

def test_feature_validator_basic_run():
    from ml.feature_validator import FeatureValidator, REQUIRED_FEATURE_KEYS, _CLAMP_RULES

    # Build values that sit inside each feature's clamp range so a genuinely
    # clean input produces no warnings (50.0 is out of range for bounded keys
    # like hour_utc/is_buy/distances).
    clean_feats = {}
    for k in REQUIRED_FEATURE_KEYS:
        if k in _CLAMP_RULES:
            lo, hi = _CLAMP_RULES[k]
            clean_feats[k] = (lo + hi) / 2
        else:
            clean_feats[k] = 50.0
    sanitized, warnings = FeatureValidator.validate_and_sanitize(clean_feats)
    
    assert isinstance(sanitized, dict)
    assert isinstance(warnings, list)
    assert len(warnings) == 0
    
    dirty_feats = clean_feats.copy()
    dirty_feats["rsi"] = float('nan')
    sanitized_dirty, warnings_dirty = FeatureValidator.validate_and_sanitize(dirty_feats)
    
    assert sanitized_dirty["rsi"] == 0.0
    assert len(warnings_dirty) > 0


# ── 5. CONFIG SMOKE ──────────────────────────────────────────────────────────

def test_config_smoke():
    from config.settings import settings
    
    max_loss = getattr(settings, "MAX_DAILY_LOSS_PCT", 0.03)
    warning = getattr(settings, "MAX_DAILY_LOSS_WARNING_PCT", 0.02)
    
    assert isinstance(max_loss, float)
    assert 0.0 < max_loss < 1.0
    assert warning < max_loss
