from decimal import Decimal
from types import SimpleNamespace
import sys

from gqos.common.enums import TradeDirection
from gqos.live.adapters import mt5_adapter
from gqos.live.adapters.mt5_adapter import MT5BrokerAdapter


class MockEventBus:
    def publish(self, envelope):
        pass


class MockOMS:
    def __init__(self):
        self.calls = []

    def callback(self, order_id, status, fill_qty, fill_price, message):
        self.calls.append((order_id, status, fill_qty, fill_price, message))


def setup_fake_mt5(monkeypatch, sent_requests, multiplier=1.0, is_probe=False):
    monkeypatch.setattr(mt5_adapter.mt5, "terminal_info", lambda: True)
    monkeypatch.setattr(mt5_adapter.mt5, "symbol_info", lambda symbol: SimpleNamespace(
        volume_step=0.01,
        volume_min=0.01,
        volume_max=100.0,
        trade_tick_size=0.01,
        point=0.01,
    ))
    monkeypatch.setattr(mt5_adapter.mt5, "account_info", lambda: SimpleNamespace(balance=9000.0))
    monkeypatch.setattr(mt5_adapter.mt5, "symbol_info_tick", lambda symbol: SimpleNamespace(ask=100.0, bid=99.9))
    monkeypatch.setattr(mt5_adapter.mt5, "ORDER_TYPE_BUY", 0, raising=False)
    monkeypatch.setattr(mt5_adapter.mt5, "ORDER_TYPE_SELL", 1, raising=False)
    monkeypatch.setattr(mt5_adapter.mt5, "ORDER_TYPE_BUY_LIMIT", 2, raising=False)
    monkeypatch.setattr(mt5_adapter.mt5, "ORDER_TYPE_SELL_LIMIT", 3, raising=False)
    monkeypatch.setattr(mt5_adapter.mt5, "TRADE_ACTION_DEAL", 1, raising=False)
    monkeypatch.setattr(mt5_adapter.mt5, "TRADE_ACTION_PENDING", 5, raising=False)
    monkeypatch.setattr(mt5_adapter.mt5, "ORDER_TIME_GTC", 0, raising=False)
    monkeypatch.setattr(mt5_adapter.mt5, "ORDER_TIME_SPECIFIED", 1, raising=False)
    monkeypatch.setattr(mt5_adapter.mt5, "ORDER_FILLING_IOC", 0, raising=False)
    monkeypatch.setattr(mt5_adapter.mt5, "ORDER_FILLING_RETURN", 2, raising=False)
    monkeypatch.setattr(mt5_adapter.mt5, "TRADE_RETCODE_DONE", 10009, raising=False)
    monkeypatch.setattr(mt5_adapter.mt5, "TRADE_RETCODE_PLACED", 10008, raising=False)

    def fake_order_send(request):
        sent_requests.append(request)
        return SimpleNamespace(
            retcode=10009,
            order=123,
            volume=request["volume"],
            price=request["price"],
        )

    monkeypatch.setattr(mt5_adapter.mt5, "order_send", fake_order_send)

    sys.modules["strategy.cooldown_manager"] = SimpleNamespace(
        cooldown_manager=SimpleNamespace(is_probe=lambda decision_id: is_probe)
    )
    sys.modules["gqos.risk.portfolio_budget"] = SimpleNamespace(
        portfolio_budget=SimpleNamespace(get_multiplier=lambda symbol: multiplier)
    )


def test_mt5_adapter_never_increases_pipeline_sized_quantity(monkeypatch):
    sent_requests = []
    setup_fake_mt5(monkeypatch, sent_requests, multiplier=1.25)
    oms = MockOMS()
    adapter = MT5BrokerAdapter(MockEventBus(), oms.callback)

    adapter.submit_order(
        "order-1",
        "EURUSDm",
        TradeDirection.BUY,
        Decimal("0.12"),
        Decimal("100.0"),
        stop_loss=Decimal("99.0"),
    )

    assert sent_requests[0]["volume"] == 0.12


def test_mt5_adapter_probe_mode_reduces_pipeline_sized_quantity(monkeypatch):
    sent_requests = []
    setup_fake_mt5(monkeypatch, sent_requests, multiplier=1.0, is_probe=True)
    oms = MockOMS()
    adapter = MT5BrokerAdapter(MockEventBus(), oms.callback)

    adapter.submit_order(
        "order-1",
        "EURUSDm",
        TradeDirection.BUY,
        Decimal("0.12"),
        Decimal("100.0"),
        stop_loss=Decimal("99.0"),
        decision_id="probe",
    )

    assert sent_requests[0]["volume"] <= 0.03
    assert sent_requests[0]["volume"] >= 0.01


def test_mt5_adapter_smart_execution_accepts_pending_placed_retcode(monkeypatch):
    sent_requests = []
    setup_fake_mt5(monkeypatch, sent_requests, multiplier=1.0)
    monkeypatch.setattr(mt5_adapter.settings, "USE_SMART_EXECUTION", True)
    monkeypatch.setattr(mt5_adapter.settings, "LIMIT_ORDER_EXPIRY_MINUTES", 5)

    def fake_order_send(request):
        sent_requests.append(request)
        return SimpleNamespace(
            retcode=10008,
            order=999,
            volume=request["volume"],
            price=request["price"],
        )

    monkeypatch.setattr(mt5_adapter.mt5, "order_send", fake_order_send)
    oms = MockOMS()
    adapter = MT5BrokerAdapter(MockEventBus(), oms.callback)

    adapter.submit_order(
        "order-1",
        "EURUSDm",
        TradeDirection.BUY,
        Decimal("0.12"),
        Decimal("100.0"),
        stop_loss=Decimal("99.0"),
        take_profit=Decimal("102.0"),
        decision_id="GQOS-20260629-ABCDEF12",
    )

    assert sent_requests[0]["action"] == 5
    assert sent_requests[0]["type"] == 2
    assert sent_requests[0]["price"] == 99.95
    assert oms.calls == [("order-1", "ACK", Decimal("0"), Decimal("0"), "MT5 Limit Accepted")]
    assert 999 in adapter._pending_orders
