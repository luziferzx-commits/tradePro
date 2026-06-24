import os
import time
from decimal import Decimal
import pandas as pd

from gqos.messaging.bus import LocalEventBus
from gqos.messaging.contracts import MessageEnvelope

from gqos.accounting.engine import AccountingEngine
from gqos.portfolio.manager import PortfolioManager
from gqos.risk.events import ExecuteTradeCommand, TradeExecutedEvent
from gqos.common.enums import TradeDirection

from gqos.live.events import OrderStatus, OrderUpdateEvent, ReconciliationFillEvent, HeartbeatEvent
from gqos.live.oms import OrderManagementSystem
from gqos.live.adapter import SandboxBrokerAdapter
from gqos.live.safety import GlobalKillSwitch, HeartbeatMonitor
from gqos.live.persistence import LedgerSnapshotService
from gqos.live.engine import LiveTradingEngine

class MockFeeModel:
    def calculate_fee(self, symbol, direction, quantity, execution_price):
        return Decimal('0'), "USD"

class MockFxConverter:
    def convert(self, amount, from_curr, to_curr):
        return amount

def test_live_trading_lifecycle_and_safety():
    bus = LocalEventBus(None)
    
    accounting = AccountingEngine(bus, MockFeeModel(), MockFxConverter())
    portfolio = PortfolioManager("LivePort", Decimal("100000.0"))
    
    oms = OrderManagementSystem(bus)
    
    def oms_callback(order_id, status, fill_qty, fill_price, msg):
        if status == "FILL":
            oms.apply_fill(order_id, fill_qty, fill_price)
        else:
            oms.update_order_status(order_id, OrderStatus(status), msg)
            
    adapter = SandboxBrokerAdapter(bus, oms_callback)
    
    safety = GlobalKillSwitch(oms, adapter)
    hb_monitor = HeartbeatMonitor(bus, safety, timeout_seconds=0.5)
    
    snapshot_path = "test_snapshot.json"
    persistence = LedgerSnapshotService(snapshot_path)
    
    engine = LiveTradingEngine(bus, oms, adapter, safety, persistence, accounting, portfolio)
    
    # Track events
    order_updates = []
    bus.subscribe(OrderUpdateEvent, lambda e: order_updates.append(e.payload))
    
    fills = []
    bus.subscribe(TradeExecutedEvent, lambda e: fills.append(e.payload))
    
    reconciliations = []
    bus.subscribe(ReconciliationFillEvent, lambda e: reconciliations.append(e.payload))
    
    # Start engine (loads empty snapshot, reconciles cleanly since broker is empty)
    engine.start()
    assert engine.is_reconciled == True
    
    adapter.start()
    
    # 1. NEW -> ACK -> PARTIAL -> FILLED lifecycle
    cmd1 = ExecuteTradeCommand(
        symbol="AAPL", direction=TradeDirection.BUY, quantity=Decimal("10.0"),
        estimated_value=Decimal("1500.0"), strategy_id="global"
    )
    bus.publish(MessageEnvelope.create(payload=cmd1, version=1))
    
    # Wait for async fills
    time.sleep(0.5)
    
    assert len(oms.orders) == 1
    o1 = list(oms.orders.values())[0]
    assert o1.status == OrderStatus.FILLED
    assert o1.filled_quantity == Decimal("10.0")
    
    # Verify partial fills updated accounting
    assert len(fills) == 2 # two 5.0 fills
    assert fills[0].quantity == Decimal("5.0")
    
    # Verify events
    statuses = [evt.status for evt in order_updates if evt.order_id == o1.order_id]
    assert OrderStatus.ACK in statuses
    assert OrderStatus.PARTIAL in statuses
    assert OrderStatus.FILLED in statuses
    
    # 2. Kill Switch blocks new orders & cancels open
    cmd2 = ExecuteTradeCommand(
        symbol="TSLA", direction=TradeDirection.BUY, quantity=Decimal("20.0"),
        estimated_value=Decimal("4000.0"), strategy_id="global"
    )
    bus.publish(MessageEnvelope.create(payload=cmd2, version=1))
    
    # Trigger disconnect on broker to prevent fills, so it stays ACK/NEW
    adapter.trigger_disconnect()
    time.sleep(0.1) # Wait for broker to reject due to disconnect
    
    # Trigger Kill Switch manually
    safety.trigger("Manual Override")
    assert safety.is_triggered == True
    
    # Try sending new order
    cmd3 = ExecuteTradeCommand(
        symbol="MSFT", direction=TradeDirection.BUY, quantity=Decimal("5.0"),
        estimated_value=Decimal("1000.0"), strategy_id="global"
    )
    bus.publish(MessageEnvelope.create(payload=cmd3, version=1))
    
    # Verify cmd3 was blocked (no MSFT order in OMS)
    msft_orders = [o for o in oms.orders.values() if o.symbol == "MSFT"]
    assert len(msft_orders) == 0
    
    # 3. Heartbeat timeout triggers halt
    safety.is_triggered = False # reset for test
    # Since we triggered disconnect, Heartbeats stop firing
    time.sleep(0.6) # Wait for heartbeat timeout (>0.5s)
    hb_monitor.check_health() # Simulate engine loop calling check_health
    assert safety.is_triggered == True # Should be triggered again by timeout
    
    # 4. Snapshot Save / Restore & Broker Truth Reconciliation
    # Save current state
    engine.save_state()
    assert os.path.exists(snapshot_path)
    
    # Create a new engine instance to simulate restart
    adapter2 = SandboxBrokerAdapter(bus, oms_callback)
    adapter2.actual_positions["AAPL"] = Decimal("15.0") # Broker says we have 15, but Ledger saved 10
    
    engine2 = LiveTradingEngine(bus, oms, adapter2, safety, persistence, accounting, portfolio)
    
    engine2.start() # Loads snapshot (10 AAPL), Reconciles against Broker (15 AAPL)
    
    # Should detect mismatch
    assert len(reconciliations) == 1
    assert reconciliations[0].quantity == Decimal("5.0")
    assert reconciliations[0].direction == TradeDirection.BUY
    
    # Engine must block trading if not reconciled
    assert engine2.is_reconciled == False
    assert safety.is_triggered == True
    
    # Cleanup
    adapter.stop()
    if os.path.exists(snapshot_path):
        os.remove(snapshot_path)

if __name__ == "__main__":
    test_live_trading_lifecycle_and_safety()
    print("M19 Live Trading tests passed!")
