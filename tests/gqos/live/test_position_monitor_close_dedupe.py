from types import SimpleNamespace

from gqos.live.position_monitor import PositionMonitor


class _Bus:
    def __init__(self):
        self.published = []

    def publish(self, event):
        self.published.append(event)


def _deal(ticket=9001, position_id=7001):
    return SimpleNamespace(
        ticket=ticket,
        position_id=position_id,
        magic=234000,
        entry=1,
        symbol="EURUSDm",
        profit=12.5,
        price=1.2345,
    )


def test_position_monitor_seeds_recent_closes_without_reemitting(monkeypatch, tmp_path):
    monkeypatch.setenv("GQOS_EMITTED_CLOSE_DEALS_PATH", str(tmp_path / "emitted_close_deals.json"))

    import MetaTrader5 as mt5

    mt5.DEAL_ENTRY_OUT = 1
    mt5.history_deals_get.return_value = [_deal()]

    monitor = PositionMonitor(None, None, None, magic_number=234000)
    bus = _Bus()
    monitor.set_event_bus(bus)

    monitor._seed_recent_closed_deals()
    monitor._check_new_deals(0, 1)

    assert bus.published == []
    assert "9001" in monitor._emitted_tickets
    assert "7001" in monitor._emitted_tickets


def test_position_monitor_emits_new_close_once(monkeypatch, tmp_path):
    monkeypatch.setenv("GQOS_EMITTED_CLOSE_DEALS_PATH", str(tmp_path / "emitted_close_deals.json"))

    import MetaTrader5 as mt5

    mt5.history_deals_get.return_value = [_deal()]

    monitor = PositionMonitor(None, None, None, magic_number=234000)
    bus = _Bus()
    monitor.set_event_bus(bus)

    monitor._check_new_deals(0, 1)
    monitor._check_new_deals(1, 2)

    assert len(bus.published) == 1
