from gqos.common.enums import TradeDirection
from decimal import Decimal
from gqos.messaging.contracts import MessageEnvelope, Command, Event
from gqos.messaging.bus import ICommandBus, IEventBus
from gqos.risk.events import ExecuteTradeCommand, RiskBudgetAllocated, RiskBudgetExhausted, TradeRejectedByRiskEvent, TradeRejectedByCircuitBreaker, TripCircuitBreakerCommand, RiskBudgetNearLimit
from gqos.risk.models import RiskBudget
from gqos.risk.store import RiskBudgetStore
from gqos.risk.engine import RiskBudgetEngine, CircuitBreakerEngine
from gqos.risk.decorator import RiskGuardedCommandBus

class MockCommandBus(ICommandBus):
    def __init__(self):
        self.published_commands = []
        
    def dispatch(self, envelope: MessageEnvelope[Command]):
        self.published_commands.append(envelope)
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

def test_circuit_breaker_blocks_trade():
    inner_bus = MockCommandBus()
    event_bus = MockEventBus()
    store = RiskBudgetStore()
    store.save(RiskBudget(budget_id="strat_cb", total_capacity=Decimal('1000.0'), utilized_capacity=Decimal('0.0')))
    
    engine = RiskBudgetEngine(store)
    cb_engine = CircuitBreakerEngine()
    
    guarded_bus = RiskGuardedCommandBus(inner_bus, event_bus, engine, cb_engine)
    
    # Trade should go through normally
    cmd = ExecuteTradeCommand(symbol="AAPL", direction=TradeDirection.BUY, quantity=Decimal('10'), estimated_value=Decimal('500.0'), strategy_id="strat_cb")
    guarded_bus.dispatch(MessageEnvelope.create(cmd, version=1))
    
    assert len(inner_bus.published_commands) == 1
    
    # Trip the circuit breaker!
    cb_engine.trip("strat_cb", reason="Daily Loss Limit Exceeded")
    
    # Trade should be blocked
    guarded_bus.dispatch(MessageEnvelope.create(cmd, version=1))
    
    # Inner bus should STILL have only 1 command (the blocked one wasn't forwarded)
    assert len(inner_bus.published_commands) == 1
    
    # An event TradeRejectedByCircuitBreaker should be emitted
    cb_rejects = [e for e in event_bus.published_events if isinstance(e.payload, TradeRejectedByCircuitBreaker)]
    assert len(cb_rejects) == 1
    assert cb_rejects[0].payload.reason == "Circuit Breaker is TRIPPED"

def test_near_limit_events_emitted():
    inner_bus = MockCommandBus()
    event_bus = MockEventBus()
    store = RiskBudgetStore()
    store.save(RiskBudget(budget_id="strat_limit", total_capacity=Decimal('100.0'), utilized_capacity=Decimal('0.0')))
    
    engine = RiskBudgetEngine(store)
    cb_engine = CircuitBreakerEngine()
    
    guarded_bus = RiskGuardedCommandBus(inner_bus, event_bus, engine, cb_engine)
    
    # Allocate 85%
    cmd1 = ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal('1'), Decimal('85.0'), "strat_limit")
    guarded_bus.dispatch(MessageEnvelope.create(cmd1, version=1))
    
    near_limit_events = [e for e in event_bus.published_events if isinstance(e.payload, RiskBudgetNearLimit)]
    assert len(near_limit_events) == 1
    assert near_limit_events[0].payload.utilized_percentage == Decimal('0.80')
    
    # Allocate 10% more (Total 95%)
    cmd2 = ExecuteTradeCommand("AAPL", TradeDirection.BUY, Decimal('1'), Decimal('10.0'), "strat_limit")
    guarded_bus.dispatch(MessageEnvelope.create(cmd2, version=1))
    
    near_limit_events = [e for e in event_bus.published_events if isinstance(e.payload, RiskBudgetNearLimit)]
    assert len(near_limit_events) == 3
    # It crossed 0.90 and 0.95 simultaneously
    percentages = [e.payload.utilized_percentage for e in near_limit_events]
    assert Decimal('0.90') in percentages
    assert Decimal('0.95') in percentages

if __name__ == "__main__":
    test_circuit_breaker_blocks_trade()
    test_near_limit_events_emitted()
    print("Circuit breaker tests passed!")
