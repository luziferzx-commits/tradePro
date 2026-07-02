"""PositionMonitor hygiene features: auto-close disabled symbols + stale exit."""
import time
from types import SimpleNamespace

import MetaTrader5 as mt5

from gqos.live.position_monitor import PositionMonitor


def _monitor():
    # evidence_router / mt5_client / indicator_calc are unused on the early-exit
    # paths under test, so None is fine.
    return PositionMonitor(None, None, None, magic_number=234000)


def _pos(symbol, opened_ts=None):
    return SimpleNamespace(
        symbol=symbol,
        type=mt5.POSITION_TYPE_BUY,
        magic=234000,
        time=opened_ts if opened_ts is not None else time.time(),
    )


def test_auto_close_disabled_symbol():
    m = _monitor()
    m._auto_close_disabled = True
    m._enabled_broker_symbols = {"EURUSDm"}
    closed = []
    m._close_position = lambda pos, reason="": closed.append((pos.symbol, reason))

    m._evaluate_single(_pos("EURGBPm"))  # disabled symbol
    assert closed and closed[0][0] == "EURGBPm"


def test_enabled_symbol_not_auto_closed():
    m = _monitor()
    m._auto_close_disabled = True
    m._enabled_broker_symbols = {"EURUSDm"}
    m._mt5_client = SimpleNamespace(get_historical_data=lambda *a, **k: None)  # stops further work
    closed = []
    m._close_position = lambda pos, reason="": closed.append(pos.symbol)

    m._evaluate_single(_pos("EURUSDm"))  # enabled symbol -> not force-closed
    assert closed == []


def test_stale_position_closed():
    m = _monitor()
    m._auto_close_disabled = False
    m._max_position_age_hours = 1.0
    closed = []
    m._close_position = lambda pos, reason="": closed.append((pos.symbol, reason))

    old = time.time() - 2 * 3600  # opened 2h ago
    m._evaluate_single(_pos("EURUSDm", opened_ts=old))
    assert closed and "Stale" in closed[0][1]


def test_fresh_position_not_stale_closed():
    m = _monitor()
    m._auto_close_disabled = False
    m._max_position_age_hours = 1.0
    m._mt5_client = SimpleNamespace(get_historical_data=lambda *a, **k: None)
    closed = []
    m._close_position = lambda pos, reason="": closed.append(pos.symbol)

    m._evaluate_single(_pos("EURUSDm", opened_ts=time.time()))  # just opened
    assert closed == []


def test_open_alert_fires_once_for_new_position(tmp_path, monkeypatch):
    import notifications.telegram_notifier as tn
    sent = []
    monkeypatch.setattr(tn, "notify_trade_executed", lambda **k: (sent.append(k), True)[1])

    m = _monitor()
    m._alerted_opens_path = str(tmp_path / "alerted.json")
    m._alerted_opens = set()

    pos = SimpleNamespace(
        symbol="EURUSDm", type=mt5.POSITION_TYPE_BUY, magic=234000,
        ticket=999, volume=0.01, price_open=1.1000, sl=1.0950, tp=1.1200,
    )
    m._alert_new_opens([pos])
    assert len(sent) == 1 and sent[0]["ticket"] == "999" and sent[0]["symbol"] == "EURUSDm"

    # Same position again -> no duplicate alert.
    m._alert_new_opens([pos])
    assert len(sent) == 1


def test_open_alert_skips_other_magic(tmp_path, monkeypatch):
    import notifications.telegram_notifier as tn
    sent = []
    monkeypatch.setattr(tn, "notify_trade_executed", lambda **k: (sent.append(k), True)[1])

    m = _monitor()
    m._alerted_opens_path = str(tmp_path / "alerted.json")
    m._alerted_opens = set()

    other = SimpleNamespace(symbol="EURUSDm", type=mt5.POSITION_TYPE_BUY, magic=999999,
                            ticket=1, volume=0.01, price_open=1.1, sl=1.0, tp=1.2)
    m._alert_new_opens([other])
    assert sent == []  # not our magic -> ignored
