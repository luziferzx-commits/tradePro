from gqos.common.enums import TradeDirection
from decimal import Decimal
from gqos.messaging.contracts import MessageEnvelope, Command, Event
from gqos.messaging.bus import ICommandBus, IEventBus
from gqos.risk.events import ExecuteTradeCommand, RiskBudgetNearLimit
from gqos.risk.models import RiskBudget
from gqos.risk.store import RiskBudgetStore
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
        self.published_events.append(envelope)
    def subscribe(self, event_type, handler) -> None:
        pass
    def unsubscribe(self, event_type, handler) -> None:
        pass

def test_near_limit_hysteresis():
    inner_bus = MockCommandBus()
    event_bus = MockEventBus()
    store = RiskBudgetStore()
    store.save(RiskBudget(budget_id="strat_hyst", total_capacity=Decimal('100.0'), utilized_capacity=Decimal('0.0')))
    
    engine = RiskBudgetEngine(store)
    cb_engine = CircuitBreakerEngine()
    guarded_bus = RiskGuardedCommandBus(inner_bus, event_bus, engine, cb_engine)
    
    # 1. Hit 91% -> Should emit 80% and 90%
    cmd1 = ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal('1'), Decimal('91.0'), "strat_hyst")
    guarded_bus.dispatch(MessageEnvelope.create(cmd1, version=1))
    
    events = [e.payload for e in event_bus.published_events if isinstance(e.payload, RiskBudgetNearLimit)]
    assert len(events) == 2
    
    event_bus.published_events.clear()
    
    # 2. Drop to 89% by releasing 2.0. (Gap is 5%, so 90 - 5 = 85. 89 > 85, so NO reset yet)
    store.release(list(store._allocations.keys())[0]) # Clear the 91.0 allocation entirely for simplicity
    store.save(RiskBudget(budget_id="strat_hyst", total_capacity=Decimal('100.0'), utilized_capacity=Decimal('89.0'), emitted_thresholds=frozenset([Decimal('0.80'), Decimal('0.90')])))
    
    # Hit 91% again -> Should NOT emit 90% because it hasn't reset
    cmd2 = ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal('1'), Decimal('2.0'), "strat_hyst")
    guarded_bus.dispatch(MessageEnvelope.create(cmd2, version=1))
    
    events = [e.payload for e in event_bus.published_events if isinstance(e.payload, RiskBudgetNearLimit)]
    assert len(events) == 0 # No new events!
    
    event_bus.published_events.clear()
    
    # 3. Drop to 84% (below 85%). Should reset the 90% threshold.
    # To properly simulate the release via store:
    alloc_id = list(store._allocations.keys())[0] # The 2.0 allocation
    store.release(alloc_id) # Drops back to 89.0
    
    # Let's force release below 85
    # The current utilized is 89. Let's create an allocation of 89 and release it entirely, but we only want to drop 5.
    store._allocations["dummy"] = ("strat_hyst", Decimal('5.0'))
    store.release("dummy") # Drops to 84.0. The 90% threshold should be reset!
    
    budget = store.get("strat_hyst")
    assert Decimal('0.90') not in budget.emitted_thresholds
    
    # Hit 91% again -> Should EMIT 90%
    cmd3 = ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal('1'), Decimal('7.0'), "strat_hyst")
    guarded_bus.dispatch(MessageEnvelope.create(cmd3, version=1))
    
    events = [e.payload for e in event_bus.published_events if isinstance(e.payload, RiskBudgetNearLimit)]
    assert len(events) == 1
    assert events[0].utilized_percentage == Decimal('0.90')

if __name__ == "__main__":
    test_near_limit_hysteresis()
    print("Hysteresis test passed!")
