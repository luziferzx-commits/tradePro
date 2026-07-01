"""DynamicScalingPolicy drawdown ladder: de-risk instead of deadlock at 10%."""
from decimal import Decimal
from types import SimpleNamespace

import pandas as pd
import pytest
import MetaTrader5 as mt5

from gqos.sizing import policies
from gqos.sizing.policies import DynamicScalingPolicy
from gqos.sizing.models import SizingRequest, InvalidSizingRequestError
from gqos.sizing.portfolio import PortfolioSnapshot
from gqos.common.enums import TradeDirection


def _policy(tmp_path, max_equity):
    p = DynamicScalingPolicy(
        base_risk_fraction=Decimal("0.01"),
        dd_derisk_pct=Decimal("0.05"),
        dd_halt_pct=Decimal("0.20"),
    )
    p.state_file = str(tmp_path / "ds.json")
    p.max_equity = Decimal(str(max_equity))
    return p


def _req():
    return SizingRequest("s1", "AAPL", TradeDirection.BUY, Decimal("100.0"), Decimal("90.0"))


def _setup_equity(monkeypatch, equity):
    monkeypatch.setattr(mt5, "account_info", lambda: SimpleNamespace(equity=equity), raising=False)
    import gqos.learning.outcome_logger as ol
    monkeypatch.setattr(ol.outcome_logger, "get_outcomes_df", lambda *a, **k: pd.DataFrame(), raising=False)


def test_drawdown_11pct_derisks_not_deadlock(tmp_path, monkeypatch):
    # 11.86% drawdown used to hard-stop at 10%; now it trades at half size.
    _setup_equity(monkeypatch, 8814.0)
    p = _policy(tmp_path, max_equity=10000.0)
    res = p.calculate_size(_req(), PortfolioSnapshot.create_mock(Decimal("8814.0")))
    assert res.quantity > 0
    assert "actual=0.005" in res.sizing_reason  # base 0.01 halved


def test_drawdown_over_halt_hard_stops(tmp_path, monkeypatch):
    _setup_equity(monkeypatch, 7000.0)  # 30% drawdown
    p = _policy(tmp_path, max_equity=10000.0)
    with pytest.raises(InvalidSizingRequestError):
        p.calculate_size(_req(), PortfolioSnapshot.create_mock(Decimal("7000.0")))


def test_small_drawdown_uses_base_risk(tmp_path, monkeypatch):
    _setup_equity(monkeypatch, 9800.0)  # 2% drawdown
    p = _policy(tmp_path, max_equity=10000.0)
    res = p.calculate_size(_req(), PortfolioSnapshot.create_mock(Decimal("9800.0")))
    assert "actual=0.01" in res.sizing_reason
