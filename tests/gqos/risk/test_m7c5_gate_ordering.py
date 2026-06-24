from gqos.common.enums import TradeDirection
from decimal import Decimal
from gqos.messaging.contracts import MessageEnvelope, Command, Event
from gqos.messaging.bus import ICommandBus, IEventBus
from gqos.risk.events import ExecuteTradeCommand, TradeRejectedByExposureLimit, RiskBudgetAllocated, RiskBudgetExhausted
from gqos.risk.assets import AssetDirectory, AssetMetadata
from gqos.risk.exposure import ExposureLimits
from gqos.risk.exposure_engine import ExposureEngine
from gqos.risk.store import RiskBudgetStore
from gqos.risk.models import RiskBudget
from gqos.risk.engine import RiskBudgetEngine, CircuitBreakerEngine
from gqos.risk.decorator import RiskGuardedCommandBus

class MockCommandBus(ICommandBus):
    def dispatch(self, envelope: MessageEnvelope[Command]):
        return "EXECUTED"
    def register_handler(self, command_type, handler) -> None:
        pass

class MockEventBus(IEventBus):
    def __init__(self):
        self.published_events = []
    def publish(self, envelope: MessageEnvelope[Event]) -> None:
        self.published_events.append(envelope.payload)
    def subscribe(self, event_type, handler) -> None:
        pass
    def unsubscribe(self, event_type, handler) -> None:
        pass

def test_gate_ordering():
    inner_bus = MockCommandBus()
    event_bus = MockEventBus()
    
    store = RiskBudgetStore()
    store.save(RiskBudget("s1", Decimal('1000.0'), Decimal('0.0')))
    engine = RiskBudgetEngine(store)
    cb_engine = CircuitBreakerEngine()
    
    directory = AssetDirectory()
    directory.register_asset(AssetMetadata("AAPL", "Tech", "Equity", "Tech"))
    
    # 1. Normal Trade
    limits = ExposureLimits(Decimal('10000.0'), Decimal('10000.0'), Decimal('10000.0'), Decimal('10000.0'), Decimal('10000.0'))
    exposure_engine = ExposureEngine(directory, limits)
    guarded_bus = RiskGuardedCommandBus(inner_bus, event_bus, engine, cb_engine, exposure_engine)
    
    cmd = ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal('1'), Decimal('100.0'), "s1")
    res = guarded_bus.dispatch(MessageEnvelope.create(cmd, version=1, correlation_id="t1"))
    
    assert res == "EXECUTED"
    assert any(isinstance(e, RiskBudgetAllocated) for e in event_bus.published_events)
    
    # 2. Blocked by Exposure (Strict limits)
    event_bus.published_events.clear()
    limits_strict = ExposureLimits(Decimal('10.0'), Decimal('10.0'), Decimal('10.0'), Decimal('10.0'), Decimal('10.0'))
    exposure_engine_strict = ExposureEngine(directory, limits_strict)
    guarded_bus_strict = RiskGuardedCommandBus(inner_bus, event_bus, engine, cb_engine, exposure_engine_strict)
    
    res2 = guarded_bus_strict.dispatch(MessageEnvelope.create(cmd, version=1, correlation_id="t2"))
    
    assert res2 is None # Blocked
    assert any(isinstance(e, TradeRejectedByExposureLimit) for e in event_bus.published_events)
    assert not any(isinstance(e, RiskBudgetAllocated) for e in event_bus.published_events)
    assert not any(isinstance(e, RiskBudgetExhausted) for e in event_bus.published_events) # Never reached budget evaluation

if __name__ == "__main__":
    test_gate_ordering()
    print("Gate Ordering Test Passed!")
