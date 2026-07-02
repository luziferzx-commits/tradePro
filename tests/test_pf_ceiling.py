"""EvidenceRouter overfit guard: reject patterns with backtest PF >= ceiling."""
from types import SimpleNamespace

import pandas as pd
import pytest

from strategy import evidence_router as er_mod
from strategy.evidence_router import EvidenceRouter


def _make_router(monkeypatch, aggregate_pf):
    router = EvidenceRouter.__new__(EvidenceRouter)  # skip heavy __init__
    router.mode = "LIVE"
    router.mt5_client = None  # skip MTF/price-action filter
    router.symbol_config = {"EURUSD": {"min_profit_factor": 1.10}}

    # Minimal feature row with the columns evaluate() touches before the gate.
    def fake_extract(df, symbol, tf):
        return pd.DataFrame([{
            "ema50": 2.0, "ema200": 1.0, "adx": 30.0,
            "atr_bucket": "MID", "adx_bucket": "MID", "trend_bucket": "UP",
        }])
    monkeypatch.setattr(er_mod.UniversalFeatureStore, "extract_features", staticmethod(fake_extract))
    monkeypatch.setattr(er_mod.SessionDetector, "detect", staticmethod(lambda ts: "London"))

    match = {
        "evidence_score": 1.0,
        "similarity_score": 0.9,
        "aggregate_pf": aggregate_pf,
        "aggregate_expectancy_r": 0.1,
        "sample_size": 300,
        "promotions": ["RESEARCH_VALIDATED"],
        "nearest_pattern": {"pattern_id": "PD_test", "horizon": 8, "regime": "TREND"},
    }
    router.similarity_engine = SimpleNamespace(
        find_similar_patterns=lambda feats, side, threshold=0.70: match if side == "LONG" else None
    )
    return router


def _df():
    return pd.DataFrame([{"time": pd.Timestamp("2026-07-02 10:00:00"), "close": 1.1, "high": 1.2, "low": 1.0}])


def test_rejects_overfit_pattern(monkeypatch):
    monkeypatch.setattr(er_mod.settings, "PATTERN_PF_CEILING", 1.5, raising=False)
    router = _make_router(monkeypatch, aggregate_pf=2.0)  # >= ceiling
    result = router.evaluate(_df(), "EURUSD", log_events=False)
    assert result is None  # rejected


def test_allows_pattern_below_ceiling(monkeypatch):
    monkeypatch.setattr(er_mod.settings, "PATTERN_PF_CEILING", 1.5, raising=False)
    router = _make_router(monkeypatch, aggregate_pf=1.2)  # in the good band
    result = router.evaluate(_df(), "EURUSD", log_events=False)
    # 1.2 is below the ceiling -> not rejected as overfit; a signal is produced.
    assert result is not None and result["symbol"] == "EURUSD"


def test_ceiling_disabled_allows_high_pf(monkeypatch):
    monkeypatch.setattr(er_mod.settings, "PATTERN_PF_CEILING", 0, raising=False)
    router = _make_router(monkeypatch, aggregate_pf=2.0)
    result = router.evaluate(_df(), "EURUSD", log_events=False)
    # With ceiling off, a high-PF pattern is not rejected for being overfit.
    assert result is not None and result["symbol"] == "EURUSD"
