import sys
import os

from gqos.messaging.bus import LocalEventBus, LocalCommandBus
from gqos.messaging.store import InMemoryEventStore
from gqos.messaging.contracts import MessageEnvelope
from gqos.risk.events import ExecuteTradeCommand, RiskBudgetAllocated, RiskBudgetExhausted, TradeRejectedByRiskEvent
from gqos.risk.models import RiskBudget
from gqos.risk.store import RiskBudgetStore
from gqos.risk.engine import RiskBudgetEngine
from gqos.risk.decorator import RiskGuardedCommandBus

def run_replay():
    print("=== M7A Risk Budget Engine Replay ===\n")
    
    logger = type("DummyLogger", (), {"log": lambda self, lvl, msg: print(f"[{lvl}] {msg}")})()
    
    event_store = InMemoryEventStore()
    event_bus = LocalEventBus(logger, event_store=event_store)
    
    inner_cmd_bus = LocalCommandBus(logger)
    
    # 1. Setup Risk Platform
    store = RiskBudgetStore()
    # Initial budget of 10,000
    store.save(RiskBudget(budget_id="strat_1", total_capacity=10000.0, utilized_capacity=0.0))
    
    engine = RiskBudgetEngine(store)
    
    # Decorator / Interceptor
    guarded_bus = RiskGuardedCommandBus(inner=inner_cmd_bus, event_bus=event_bus, engine=engine)
    
    # 2. Setup Plugin (Mock Broker/Executor)
    def dummy_executor(env: MessageEnvelope[ExecuteTradeCommand]):
        print(f"  -> Plugin Executing Trade: {env.payload.symbol} for ${env.payload.estimated_value}")
        
    inner_cmd_bus.register_handler(ExecuteTradeCommand, dummy_executor)
    
    # 3. Setup Observers
    def on_allocated(env: MessageEnvelope[RiskBudgetAllocated]):
        p = env.payload
        print(f"  -> [RISK EVENT] Allocated: ${p.allocated_amount} (Utilized: ${p.new_utilized_capacity} / ${p.total_capacity})")
        
    def on_exhausted(env: MessageEnvelope[RiskBudgetExhausted]):
        p = env.payload
        print(f"  -> [RISK EVENT] Exhausted! Requested: ${p.requested_amount}, Remaining Capacity: ${p.total_capacity - p.current_utilized}")
        
    def on_rejected(env: MessageEnvelope[TradeRejectedByRiskEvent]):
        p = env.payload
        print(f"  -> [RISK EVENT] Trade Rejected: {p.symbol} - {p.reason}")
        
    event_bus.subscribe(RiskBudgetAllocated, on_allocated)
    event_bus.subscribe(RiskBudgetExhausted, on_exhausted)
    event_bus.subscribe(TradeRejectedByRiskEvent, on_rejected)
    
    # 4. Dispatch Commands
    print("\n--- Dispatching Trade 1: $4,000 ---")
    guarded_bus.dispatch(MessageEnvelope.create(
        ExecuteTradeCommand("AAPL", 20, 4000.0, "strat_1"), version=1, correlation_id="trade_1"
    ))
    
    print("\n--- Dispatching Trade 2: $4,000 ---")
    guarded_bus.dispatch(MessageEnvelope.create(
        ExecuteTradeCommand("TSLA", 20, 4000.0, "strat_1"), version=1, correlation_id="trade_2"
    ))
    
    print("\n--- Dispatching Trade 3: $4,000 (Should Deny) ---")
    guarded_bus.dispatch(MessageEnvelope.create(
        ExecuteTradeCommand("NVDA", 10, 4000.0, "strat_1"), version=1, correlation_id="trade_3"
    ))
    
    print("\n--- Releasing Budget: $3,000 ---")
    success, budget = engine.release_allocation("strat_1", 3000.0)
    print(f"  -> Released $3,000. New Utilized: ${budget.utilized_capacity} / ${budget.total_capacity}")
    
    print("\n--- Dispatching Trade 4: $4,000 (Should Allow) ---")
    guarded_bus.dispatch(MessageEnvelope.create(
        ExecuteTradeCommand("MSFT", 10, 4000.0, "strat_1"), version=1, correlation_id="trade_4"
    ))
    
    # 5. Print Ledger
    print("\n=== EventStore Ledger (Chronological) ===")
    for env in event_store.get_all():
        event_name = type(env.payload).__name__
        print(f"[{env.sequence_number}] {event_name} (Corr: {env.correlation_id})")

if __name__ == "__main__":
    run_replay()
