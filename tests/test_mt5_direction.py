from types import SimpleNamespace

import MetaTrader5 as mt5

from dashboard.utils.data_loader import get_trade_history
from execution.mt5_direction import closing_deal_position_direction


def test_closing_deal_direction_is_original_position_side():
    mt5.DEAL_TYPE_BUY = 0
    mt5.DEAL_TYPE_SELL = 1

    assert closing_deal_position_direction(mt5.DEAL_TYPE_SELL) == "BUY"
    assert closing_deal_position_direction(mt5.DEAL_TYPE_BUY) == "SELL"


def test_dashboard_trade_history_uses_position_direction(monkeypatch):
    mt5.DEAL_ENTRY_OUT = 1
    mt5.DEAL_TYPE_BUY = 0
    mt5.DEAL_TYPE_SELL = 1

    monkeypatch.setattr("dashboard.utils.data_loader.init_mt5", lambda: True)
    mt5.history_deals_get.return_value = [
        SimpleNamespace(
            ticket=101,
            symbol="EURUSDm",
            type=mt5.DEAL_TYPE_SELL,
            entry=mt5.DEAL_ENTRY_OUT,
            volume=0.1,
            price=1.2,
            profit=5.0,
            time=1,
        ),
        SimpleNamespace(
            ticket=102,
            symbol="GBPUSDm",
            type=mt5.DEAL_TYPE_BUY,
            entry=mt5.DEAL_ENTRY_OUT,
            volume=0.2,
            price=1.3,
            profit=-2.0,
            time=2,
        ),
    ]

    history = get_trade_history(days=1)

    assert [row["direction"] for row in history] == ["BUY", "SELL"]
