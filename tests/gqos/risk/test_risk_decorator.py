from gqos.common.enums import TradeDirection
import pytest
from typing import List
from gqos.messaging.contracts import MessageEnvelope, Command, Event
from gqos.messaging.bus import ICommandBus, IEventBus
from gqos.risk.events import ExecuteTradeCommand, RiskBudgetAllocated, RiskBudgetExhausted, TradeRejectedByRiskEvent
from gqos.risk.models import RiskBudget
from gqos.risk.store import RiskBudgetStore
from gqos.risk.engine import RiskBudgetEngine
from gqos.risk.decorator import RiskGuardedCommandBus

class MockCommandBus(ICommandBus):
    def __init__(self):
        self.published_commands: List[MessageEnvelope] = []
        
    def dispatch(self, envelope: MessageEnvelope[Command]):
        self.published_commands.append(envelope)
        return None
        
    def register_handler(self, command_type, handler) -> None:
        pass

class MockEventBus(IEventBus):
    def __init__(self):
        self.published_events: List[MessageEnvelope] = []
        
    def publish(self, envelope: MessageEnvelope[Event]) -> None:
        self.published_events.append(envelope)
        
    def subscribe(self, event_type, handler) -> None:
        pass
        
    def unsubscribe(self, event_type, handler) -> None:
        pass

def test_risk_guarded_bus_allows_trade():
    inner_bus = MockCommandBus()
    event_bus = MockEventBus()
    store = RiskBudgetStore()
    store.save(RiskBudget(budget_id="strat_1", total_capacity=1000.0, utilized_capacity=0.0))
    engine = RiskBudgetEngine(store)
    
    guarded_bus = RiskGuardedCommandBus(inner_bus, event_bus, engine)
    
    cmd = ExecuteTradeCommand(symbol="AAPL", direction=TradeDirection.BUY, quantity=10, estimated_value=500.0, strategy_id="strat_1")
    env = MessageEnvelope.create(cmd, version=1)
    
    guarded_bus.dispatch(env)
    
    # Should be forwarded
    assert len(inner_bus.published_commands) == 1
    
    # Should emit RiskBudgetAllocated
    assert len(event_bus.published_events) == 1
    assert isinstance(event_bus.published_events[0].payload, RiskBudgetAllocated)
    assert event_bus.published_events[0].payload.allocated_amount == 500.0

def test_risk_guarded_bus_denies_trade():
    inner_bus = MockCommandBus()
    event_bus = MockEventBus()
    store = RiskBudgetStore()
    store.save(RiskBudget(budget_id="strat_1", total_capacity=1000.0, utilized_capacity=800.0))
    engine = RiskBudgetEngine(store)
    
    guarded_bus = RiskGuardedCommandBus(inner_bus, event_bus, engine)
    
    cmd = ExecuteTradeCommand(symbol="AAPL", direction=TradeDirection.BUY, quantity=10, estimated_value=500.0, strategy_id="strat_1")
    env = MessageEnvelope.create(cmd, version=1)
    
    guarded_bus.dispatch(env)
    
    # Should NOT be forwarded
    assert len(inner_bus.published_commands) == 0
    
    # Should emit RiskBudgetExhausted and TradeRejectedByRiskEvent
    assert len(event_bus.published_events) == 2
    payloads = [e.payload for e in event_bus.published_events]
    assert any(isinstance(p, RiskBudgetExhausted) for p in payloads)
    assert any(isinstance(p, TradeRejectedByRiskEvent) for p in payloads)

def test_risk_guarded_bus_ignores_other_commands():
    inner_bus = MockCommandBus()
    event_bus = MockEventBus()
    store = RiskBudgetStore()
    engine = RiskBudgetEngine(store)
    
    guarded_bus = RiskGuardedCommandBus(inner_bus, event_bus, engine)
    
    class OtherCommand(Command):
        pass
        
    cmd = OtherCommand()
    env = MessageEnvelope.create(cmd, version=1)
    
    guarded_bus.dispatch(env)
    
    # Should be forwarded directly
    assert len(inner_bus.published_commands) == 1
    assert len(event_bus.published_events) == 0
