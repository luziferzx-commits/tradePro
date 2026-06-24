import os
import json
from decimal import Decimal

from gqos.messaging.bus import LocalEventBus
from gqos.messaging.contracts import MessageEnvelope
from gqos.common.enums import TradeDirection

from gqos.risk.events import TradeExecutedEvent
from gqos.paper.events import MarketDataEvent

from gqos.ops.audit import AuditLogWriter
from gqos.ops.replay import ReplayEngine
from gqos.ops.logging import get_structured_logger
from gqos.ops.metrics import MetricsExporter

def test_m20_ops_observability():
    # 1. Test Structured Logger
    logger = get_structured_logger("test_ops")
    # We can't easily intercept stdout without pytest capsys, but we know it won't crash
    logger.info("Test message", extra={"correlation_id": "corr-123", "metadata": {"order": "1"}})
    
    # 2. Test Prometheus Metrics
    metrics = MetricsExporter()
    metrics.total_orders.labels(strategy="global").inc()
    metrics.live_equity.labels(portfolio_id="LivePort").set(100500.0)
    
    # Assert values (using _value for test inspection)
    assert metrics.total_orders.labels(strategy="global")._value.get() == 1.0
    assert metrics.live_equity.labels(portfolio_id="LivePort")._value.get() == 100500.0
    
    # 3. Test Audit Log Writer
    audit_file = "test_audit.jsonl"
    if os.path.exists(audit_file):
        os.remove(audit_file)
        
    bus = LocalEventBus(logger=None)
    audit_writer = AuditLogWriter(bus, filepath=audit_file)
    
    # Send a Trade
    trade = TradeExecutedEvent(
        strategy_id="global",
        symbol="AAPL",
        direction=TradeDirection.BUY,
        quantity=Decimal("10.0"),
        execution_price=Decimal("150.0"),
        intended_price=Decimal("150.0"),
        slippage_amount=Decimal("0.0")
    )
    
    env1 = MessageEnvelope.create(trade, version=1, correlation_id="trade-1")
    audit_writer.append(env1)
    
    # Send a Tick (should be ignored)
    tick = MarketDataEvent(symbol="AAPL", price=151.0, timestamp=0.0)
    env2 = MessageEnvelope.create(tick, version=1)
    audit_writer.append(env2)
    
    prod_hash = audit_writer.get_current_state_hash()
    
    # Verify file contents
    with open(audit_file, 'r') as f:
        lines = f.readlines()
        assert len(lines) == 1 # Only trade, no tick
        
        entry = json.loads(lines[0])
        assert entry["event_type"] == "TradeExecutedEvent"
        assert entry["correlation_id"] == "trade-1"
        assert "hash" in entry
        
    # 4. Test Event Replay Engine
    replay_engine = ReplayEngine(audit_file)
    replay_hash = replay_engine.replay()
    
    # Hash verification
    assert replay_hash == prod_hash, "Replay Hash does not match Production Hash!"
    
    # State reconstruction verification
    assert len(replay_engine.accounting.state.positions) == 1
    pos = replay_engine.accounting.state.positions["global_AAPL"]
    assert pos.quantity == Decimal("10.0")
    
    # Cleanup
    if os.path.exists(audit_file):
        os.remove(audit_file)

if __name__ == "__main__":
    test_m20_ops_observability()
    print("M20 Operations tests passed!")
