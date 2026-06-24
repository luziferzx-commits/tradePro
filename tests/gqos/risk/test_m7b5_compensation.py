from gqos.common.enums import TradeDirection
from decimal import Decimal
from gqos.messaging.contracts import MessageEnvelope, Command, Event
from gqos.messaging.bus import ICommandBus, IEventBus
from gqos.risk.events import ExecuteTradeCommand, RiskBudgetAllocated, RiskBudgetReleased
from gqos.risk.models import RiskBudget
from gqos.risk.store import RiskBudgetStore
from gqos.risk.engine import RiskBudgetEngine, CircuitBreakerEngine
from gqos.risk.decorator import RiskGuardedCommandBus

class FailingMockCommandBus(ICommandBus):
    def dispatch(self, envelope: MessageEnvelope[Command]):
        raise RuntimeError("Plugin Failed")
        
    def register_handler(self, command_type, handler) -> None:
        pass

class MockEventBus(IEventBus):
    def __init__(self):
        self.published_events = []
        
    def publish(self, envelope: MessageEnvelope[Event]) -> None:
        self.published_events.append(envelope)
        
    def subscribe(self, event_type, handler) -> None:
        pass
        
    def unsubscribe(self, event_type, handler) -> None:
        pass

def test_compensation_on_plugin_failure():
    inner_bus = FailingMockCommandBus()
    event_bus = MockEventBus()
    store = RiskBudgetStore()
    store.save(RiskBudget(budget_id="strat_comp", total_capacity=Decimal('100.0'), utilized_capacity=Decimal('0.0')))
    
    engine = RiskBudgetEngine(store)
    cb_engine = CircuitBreakerEngine()
    guarded_bus = RiskGuardedCommandBus(inner_bus, event_bus, engine, cb_engine)
    
    cmd = ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal('1'), Decimal('50.0'), "strat_comp")
    env = MessageEnvelope.create(cmd, version=1)
    
    try:
        guarded_bus.dispatch(env)
    except RuntimeError:
        pass # Expected
        
    # Budget should have been released
    budget = store.get("strat_comp")
    assert budget.utilized_capacity == Decimal('0.0')
    
    # Check events emitted
    payloads = [e.payload for e in event_bus.published_events]
    
    # 1. Allocated
    allocated = [p for p in payloads if isinstance(p, RiskBudgetAllocated)]
    assert len(allocated) == 1
    assert allocated[0].allocated_amount == Decimal('50.0')
    
    # 2. Released (Compensation)
    released = [p for p in payloads if isinstance(p, RiskBudgetReleased)]
    assert len(released) == 1
    assert released[0].released_amount == Decimal('50.0')

if __name__ == "__main__":
    test_compensation_on_plugin_failure()
    print("Compensation test passed!")
