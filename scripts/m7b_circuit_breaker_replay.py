import uuid
from decimal import Decimal
from gqos.messaging.bus import LocalEventBus, LocalCommandBus
from gqos.messaging.store import InMemoryEventStore
from gqos.messaging.contracts import MessageEnvelope
from gqos.risk.events import ExecuteTradeCommand, RiskBudgetAllocated, RiskBudgetExhausted, TradeRejectedByRiskEvent, TradeRejectedByCircuitBreaker, RiskBudgetNearLimit
from gqos.risk.models import RiskBudget
from gqos.risk.store import RiskBudgetStore
from gqos.risk.engine import RiskBudgetEngine, CircuitBreakerEngine
from gqos.risk.decorator import RiskGuardedCommandBus

def run_replay():
    print("=== M7B Circuit Breaker Replay ===\n")
    
    logger = type("DummyLogger", (), {"log": lambda self, lvl, msg: print(f"[{lvl}] {msg}")})()
    
    event_store = InMemoryEventStore()
    event_bus = LocalEventBus(logger, event_store=event_store)
    inner_cmd_bus = LocalCommandBus(logger)
    
    store = RiskBudgetStore()
    store.save(RiskBudget(budget_id="strat_cb_test", total_capacity=Decimal('10000.0'), utilized_capacity=Decimal('0.0')))
    
    engine = RiskBudgetEngine(store)
    cb_engine = CircuitBreakerEngine()
    
    guarded_bus = RiskGuardedCommandBus(inner=inner_cmd_bus, event_bus=event_bus, engine=engine, cb_engine=cb_engine)
    
    # Plugin
    def dummy_executor(env: MessageEnvelope[ExecuteTradeCommand]):
        print(f"  -> Plugin Executing Trade: {env.payload.symbol} for ${env.payload.estimated_value}")
    inner_cmd_bus.register_handler(ExecuteTradeCommand, dummy_executor)
    
    # Observers
    def on_near_limit(env: MessageEnvelope[RiskBudgetNearLimit]):
        p = env.payload
        print(f"  -> [RISK EVENT] Near Limit! Crossed {p.utilized_percentage * 100}% threshold.")
        
    def on_cb_reject(env: MessageEnvelope[TradeRejectedByCircuitBreaker]):
        p = env.payload
        print(f"  -> [RISK EVENT] BLOCK: Trade Rejected by Circuit Breaker - {p.reason}")
        
    event_bus.subscribe(RiskBudgetNearLimit, on_near_limit)
    event_bus.subscribe(TradeRejectedByCircuitBreaker, on_cb_reject)
    
    print("\n--- Dispatching Trade 1: $5,000 (Normal) ---")
    guarded_bus.dispatch(MessageEnvelope.create(
        ExecuteTradeCommand("AAPL", Decimal('10'), Decimal('5000.0'), "strat_cb_test"), version=1, correlation_id="t1"
    ))
    
    print("\n--- Dispatching Trade 2: $4,000 (Hits 90% threshold) ---")
    guarded_bus.dispatch(MessageEnvelope.create(
        ExecuteTradeCommand("TSLA", Decimal('10'), Decimal('4000.0'), "strat_cb_test"), version=1, correlation_id="t2"
    ))
    
    print("\n--- [RiskMonitor] Daily Loss Limit Reached! Tripping Circuit Breaker... ---")
    cb_engine.trip("strat_cb_test", "Daily Loss Exceeded 2%")
    print("  -> Circuit Breaker TRIPPED.")
    
    print("\n--- Dispatching Trade 3: $500 (Normally allowed, but CB is tripped) ---")
    guarded_bus.dispatch(MessageEnvelope.create(
        ExecuteTradeCommand("NVDA", Decimal('1'), Decimal('500.0'), "strat_cb_test"), version=1, correlation_id="t3"
    ))
    
    print("\n=== EventStore Ledger (Chronological) ===")
    for env in event_store.get_all():
        event_name = type(env.payload).__name__
        print(f"[{env.sequence_number}] {event_name} (Corr: {env.correlation_id})")

if __name__ == "__main__":
    run_replay()
