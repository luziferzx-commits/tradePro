"""tests/test_sl_tp_calculator.py — Unit tests for SLTPCalculator."""
import pytest
import math
import pandas as pd
from risk.sl_tp_calculator import SLTPCalculator, MIN_SL_POINTS, MAX_SL_POINTS, FALLBACK_ATR


def make_df(atr_value: float) -> pd.DataFrame:
    """Helper to create a minimal DataFrame with an 'atr' column."""
    return pd.DataFrame({"atr": [atr_value]})


def test_normal_atr():
    """1. df with atr=18.5, expect sl_points between MIN and MAX, tp_points = sl_points * rr_ratio."""
    df = make_df(18.5)
    rr_ratio = 2.0
    result = SLTPCalculator.calculate(df, direction="BUY", atr_multiplier_sl=1.8, rr_ratio=rr_ratio)
    
    assert MIN_SL_POINTS <= result["sl_points"] <= MAX_SL_POINTS
    assert result["tp_points"] == int(round(result["sl_points"] * rr_ratio))
    assert result["atr_used"] == 18.5


def test_zero_atr():
    """2. df with atr=0.0, expect fallback used, sl_points valid."""
    df = make_df(0.0)
    result = SLTPCalculator.calculate(df, direction="BUY")
    
    assert result["atr_used"] == FALLBACK_ATR
    assert MIN_SL_POINTS <= result["sl_points"] <= MAX_SL_POINTS


def test_nan_atr():
    """3. df with atr=NaN, expect fallback used, no crash."""
    df = make_df(float('nan'))
    result = SLTPCalculator.calculate(df, direction="SELL")
    
    assert result["atr_used"] == FALLBACK_ATR
    assert MIN_SL_POINTS <= result["sl_points"] <= MAX_SL_POINTS


def test_very_high_atr():
    """4. df with atr=250.0, expect sl_points clamped to MAX_SL_POINTS=2000."""
    df = make_df(250.0)
    # SL would normally be 250 * 1.8 / 0.01 = 45000, which should clamp to 2000
    result = SLTPCalculator.calculate(df, direction="BUY", atr_multiplier_sl=1.8)
    
    assert result["sl_points"] == MAX_SL_POINTS


def test_very_low_atr():
    """5. df with atr=0.5, expect sl_points clamped to MIN_SL_POINTS=150."""
    df = make_df(0.5)
    # SL would normally be 0.5 * 1.8 / 0.01 = 90, which should clamp to 150
    result = SLTPCalculator.calculate(df, direction="SELL", atr_multiplier_sl=1.8)
    
    assert result["sl_points"] == MIN_SL_POINTS


def test_rr_ratio_custom():
    """6. atr=20.0, rr_ratio=3.0, expect tp_points = sl_points * 3."""
    df = make_df(20.0)
    result = SLTPCalculator.calculate(df, direction="BUY", atr_multiplier_sl=1.8, rr_ratio=3.0)
    
    assert result["tp_points"] == result["sl_points"] * 3


def test_atr_regime_low():
    """7. atr=8.0, expect get_atr_regime() returns 'LOW'."""
    assert SLTPCalculator.get_atr_regime(8.0) == "LOW"


def test_atr_regime_normal():
    """8. atr=20.0, expect returns 'NORMAL'."""
    assert SLTPCalculator.get_atr_regime(20.0) == "NORMAL"


def test_atr_regime_high():
    """9. atr=45.0, expect returns 'HIGH'."""
    assert SLTPCalculator.get_atr_regime(45.0) == "HIGH"


def test_return_keys():
    """10. verify returned dict has all 5 keys."""
    df = make_df(15.0)
    result = SLTPCalculator.calculate(df, direction="BUY")
    
    expected_keys = {"sl_points", "tp_points", "atr_used", "atr_regime", "rr_ratio"}
    assert set(result.keys()) == expected_keys
