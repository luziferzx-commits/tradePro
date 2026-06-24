from gqos.common.enums import TradeDirection
from decimal import Decimal
from gqos.messaging.contracts import MessageEnvelope, Command, Event
from gqos.messaging.bus import ICommandBus, IEventBus
from gqos.risk.events import ExecuteTradeCommand, TradeRejectedByExposureLimit, RiskBudgetAllocated
from gqos.risk.assets import AssetDirectory, AssetMetadata
from gqos.risk.exposure import ExposureLimits
from gqos.risk.exposure_engine import ExposureEngine
from gqos.risk.store import RiskBudgetStore
from gqos.risk.models import RiskBudget
from gqos.risk.engine import RiskBudgetEngine, CircuitBreakerEngine
from gqos.risk.decorator import RiskGuardedCommandBus

class MockCommandBus(ICommandBus):
    def dispatch(self, envelope: MessageEnvelope[Command]):
        return None
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

def test_bus_integration_exposure():
    inner_bus = MockCommandBus()
    event_bus = MockEventBus()
    
    store = RiskBudgetStore()
    store.save(RiskBudget("s1", Decimal('1000.0'), Decimal('0.0')))
    engine = RiskBudgetEngine(store)
    cb_engine = CircuitBreakerEngine()
    
    directory = AssetDirectory()
    directory.register_asset(AssetMetadata("AAPL", "Tech", "Equity", "Tech"))
    
    limits = ExposureLimits(Decimal('100.0'), Decimal('100.0'), Decimal('100.0'), Decimal('100.0'), Decimal('100.0'))
    exposure_engine = ExposureEngine(directory, limits)
    
    guarded_bus = RiskGuardedCommandBus(inner_bus, event_bus, engine, cb_engine, exposure_engine)
    
    # 1. Dispatch trade over limit (200.0)
    cmd = ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal('10'), Decimal('200.0'), "s1")
    guarded_bus.dispatch(MessageEnvelope.create(cmd, version=1))
    
    # Check that it was blocked
    rejections = [e for e in event_bus.published_events if isinstance(e, TradeRejectedByExposureLimit)]
    assert len(rejections) == 1
    
    # Check that NO RiskBudgetAllocated was emitted
    allocations = [e for e in event_bus.published_events if isinstance(e, RiskBudgetAllocated)]
    assert len(allocations) == 0

if __name__ == "__main__":
    test_bus_integration_exposure()
    print("Bus integration test passed!")
