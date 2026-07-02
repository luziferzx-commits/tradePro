import pytest
import time
from decimal import Decimal

from gqos.common.enums import TradeDirection
from gqos.messaging.bus import LocalEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.live.events import OrderStatus, OrderAdjustedEvent
from gqos.live.adapters.binance import BinanceAdapter
from gqos.live.adapters.factory import AdapterFactory
from gqos.live.adapter import SandboxBrokerAdapter
from gqos.config.secrets import LocalEnvSecretsProvider
from gqos.config.settings import GQOSSettings

class MockOMS:
    def __init__(self):
        self.last_status = None
        self.last_fill_qty = Decimal('0')
        self.last_fill_price = Decimal('0')
        self.calls = 0
        
    def oms_callback(self, order_id, status, fill_qty, fill_price, message):
        self.calls += 1
        self.last_status = status
        if fill_qty is not None:
            self.last_fill_qty += fill_qty
            self.last_fill_price = fill_price

@pytest.fixture
def secrets_provider():
    settings = GQOSSettings(broker_api_key="test_key", broker_api_secret="test_secret")
    return LocalEnvSecretsProvider(settings)

import logging

@pytest.fixture
def event_bus():
    return LocalEventBus(logger=logging.getLogger("test"))

def test_adapter_factory(event_bus, secrets_provider):
    oms = MockOMS()
    
    sandbox = AdapterFactory.create_adapter("sandbox", event_bus, oms.oms_callback, secrets_provider)
    assert isinstance(sandbox, SandboxBrokerAdapter)
    
    binance = AdapterFactory.create_adapter("binance_testnet", event_bus, oms.oms_callback, secrets_provider)
    assert isinstance(binance, BinanceAdapter)
    
    with pytest.raises(ValueError):
        AdapterFactory.create_adapter("unknown", event_bus, oms.oms_callback, secrets_provider)

def test_binance_status_mapping(event_bus, secrets_provider):
    adapter = BinanceAdapter(event_bus, MockOMS().oms_callback, secrets_provider, testnet=True)
    
    assert adapter._map_status("NEW") == OrderStatus.NEW
    assert adapter._map_status("PARTIALLY_FILLED") == OrderStatus.PARTIAL
    assert adapter._map_status("FILLED") == OrderStatus.FILLED
    assert adapter._map_status("CANCELED") == OrderStatus.CANCELLED
    assert adapter._map_status("UNKNOWN") == OrderStatus.REJECTED

def test_binance_precision_adjustment(event_bus, secrets_provider):
    oms = MockOMS()
    adapter = BinanceAdapter(event_bus, oms.oms_callback, secrets_provider, testnet=True)

    # MetadataCache is empty until refresh() hits the network; seed the BTCUSDT
    # exchange filters directly so this stays a hermetic unit test.
    adapter._metadata.rules["BTCUSDT"] = {
        "tick_size": Decimal("0.10"),
        "step_size": Decimal("0.001"),
    }

    adjusted_events = []
    event_bus.subscribe(OrderAdjustedEvent, lambda env: adjusted_events.append(env.payload))

    # BTCUSDT tick_size is 0.10, step_size is 0.001
    adapter.submit_order("ORD-1", "BTCUSDT", TradeDirection.BUY, Decimal("1.2345"), Decimal("50000.123"))
    
    # Need to wait briefly as submit_order spawns threads
    time.sleep(0.1)
    
    assert len(adjusted_events) == 1
    evt = adjusted_events[0]
    assert evt.original_quantity == Decimal("1.2345")
    assert evt.adjusted_quantity == Decimal("1.234") # rounded to 0.001
    assert evt.original_price == Decimal("50000.123")
    assert evt.adjusted_price == Decimal("50000.10") # rounded to 0.10

def test_binance_partial_fill_payload(event_bus, secrets_provider):
    oms = MockOMS()
    adapter = BinanceAdapter(event_bus, oms.oms_callback, secrets_provider, testnet=True)
    
    # Simulate first payload
    payload1 = {"e": "executionReport", "c": "ORD-2", "X": "PARTIALLY_FILLED", "l": "0.5", "L": "50000"}
    adapter._handle_ws_message(payload1)
    
    assert oms.last_status == "FILL"
    assert oms.last_fill_qty == Decimal('0.5')
    
    # Final payload
    payload2 = {"e": "executionReport", "c": "ORD-2", "X": "FILLED", "l": "0.5", "L": "50000"}
    adapter._handle_ws_message(payload2)
    
    assert oms.last_fill_qty == Decimal('1.0')

def test_binance_websocket_disconnect(event_bus, secrets_provider):
    oms = MockOMS()
    adapter = BinanceAdapter(event_bus, oms.oms_callback, secrets_provider, testnet=True)
    
    adapter.trigger_disconnect()
    
    # Submitting while disconnected
    adapter.submit_order("ORD-3", "ETHUSDT", TradeDirection.BUY, Decimal("10"), Decimal("2000"))
    assert oms.last_status == OrderStatus.REJECTED.value
    
    with pytest.raises(ConnectionError):
        adapter.cancel_order("ORD-3")

def test_binance_startup_reconciliation(event_bus, secrets_provider):
    adapter = BinanceAdapter(event_bus, MockOMS().oms_callback, secrets_provider, testnet=True)
    
    positions = adapter.get_actual_positions()
    assert positions["BTCUSDT"] == Decimal("1.5")
    assert positions["ETHUSDT"] == Decimal("10.0")

if __name__ == "__main__":
    pytest.main(["-v", __file__])
