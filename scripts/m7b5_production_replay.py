import time
from decimal import Decimal
from gqos.messaging.bus import LocalEventBus, LocalCommandBus
from gqos.messaging.store import InMemoryEventStore
from gqos.messaging.contracts import MessageEnvelope
from gqos.risk.events import (
    ExecuteTradeCommand, CircuitBreakerTripped, TradeRejectedByCircuitBreaker, 
    TripCircuitBreakerCommand, CircuitBreakerHalfOpened, TestCircuitBreakerCommand,
    CircuitBreakerReset, ResetCircuitBreakerCommand
)
from gqos.risk.models import RiskBudget
from gqos.risk.store import RiskBudgetStore
from gqos.risk.engine import RiskBudgetEngine, CircuitBreakerEngine
from gqos.risk.decorator import RiskGuardedCommandBus

def run_replay():
    print("=== M7B.5 Production Hardening Replay ===")
    
    logger = type("DummyLogger", (), {"log": lambda self, lvl, msg: print(f"[{lvl}] {msg}")})()
    
    event_store = InMemoryEventStore()
    event_bus = LocalEventBus(logger, event_store=event_store)
    inner_cmd_bus = LocalCommandBus(logger)
    
    store = RiskBudgetStore()
    store.save(RiskBudget(budget_id="strat_prod", total_capacity=Decimal('10000.0'), utilized_capacity=Decimal('0.0')))
    
    engine = RiskBudgetEngine(store)
    cb_engine = CircuitBreakerEngine()
    guarded_bus = RiskGuardedCommandBus(inner_cmd_bus, event_bus, engine, cb_engine)
    
    # Plugin
    def dummy_executor(env: MessageEnvelope[ExecuteTradeCommand]):
        print(f"  -> Plugin Executing Trade: {env.payload.symbol}")
    inner_cmd_bus.register_handler(ExecuteTradeCommand, dummy_executor)
    
    # Observers
    event_bus.subscribe(TradeRejectedByCircuitBreaker, lambda e: print(f"  -> [BLOCK] {e.payload.reason}"))
    event_bus.subscribe(CircuitBreakerTripped, lambda e: print("  -> [STATE] Circuit Breaker OPEN"))
    
    # Run
    print("\n[Phase 1] Normal Operation")
    guarded_bus.dispatch(MessageEnvelope.create(ExecuteTradeCommand("AAPL", Decimal('10'), Decimal('100.0'), "strat_prod"), version=1, correlation_id="t1"))
    
    print("\n[Phase 2] Trip Circuit Breaker")
    cb_engine.trip("strat_prod", "Catastrophic Failure")
    event_bus.publish(MessageEnvelope.create(CircuitBreakerTripped("strat_prod", "Catastrophic Failure"), version=1)) # Manually log event for rebuild
    
    print("\n[Phase 3] Try Trading")
    guarded_bus.dispatch(MessageEnvelope.create(ExecuteTradeCommand("TSLA", Decimal('10'), Decimal('100.0'), "strat_prod"), version=1, correlation_id="t2"))
    
    print("\n[Phase 4] System Crash and Restart")
    print("  -> Creating fresh engines...")
    # Simulate restart
    new_cb_engine = CircuitBreakerEngine()
    new_guarded_bus = RiskGuardedCommandBus(inner_cmd_bus, event_bus, engine, new_cb_engine)
    
    # Rebuild from EventStore
    events = event_store.get_all()
    new_cb_engine.rebuild_from_events(events)
    print("  -> Rebuilt Circuit Breaker state from EventStore")
    
    print("\n[Phase 5] Try Trading After Restart")
    new_guarded_bus.dispatch(MessageEnvelope.create(ExecuteTradeCommand("NVDA", Decimal('10'), Decimal('100.0'), "strat_prod"), version=1, correlation_id="t3"))

if __name__ == "__main__":
    run_replay()
