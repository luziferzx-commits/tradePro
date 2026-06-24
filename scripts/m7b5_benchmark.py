import time
from decimal import Decimal
from gqos.messaging.bus import LocalEventBus, LocalCommandBus
from gqos.messaging.store import InMemoryEventStore
from gqos.messaging.contracts import MessageEnvelope
from gqos.risk.events import ExecuteTradeCommand
from gqos.risk.models import RiskBudget, AllocationRequest
from gqos.risk.store import RiskBudgetStore
from gqos.risk.engine import RiskBudgetEngine, CircuitBreakerEngine
from gqos.risk.decorator import RiskGuardedCommandBus

def run_benchmarks():
    print("=== M7B.5 Production Hardening Benchmarks ===")
    
    logger = type("DummyLogger", (), {"log": lambda self, lvl, msg: None})()
    event_store = InMemoryEventStore()
    event_bus = LocalEventBus(logger, event_store=event_store)
    inner_cmd_bus = LocalCommandBus(logger)
    
    # Plugin
    inner_cmd_bus.register_handler(ExecuteTradeCommand, lambda e: None)
    
    store = RiskBudgetStore()
    store.save(RiskBudget(budget_id="bench", total_capacity=Decimal('1000000.0'), utilized_capacity=Decimal('0.0')))
    
    engine = RiskBudgetEngine(store)
    cb_engine = CircuitBreakerEngine()
    guarded_bus = RiskGuardedCommandBus(inner_cmd_bus, event_bus, engine, cb_engine)

    ITERATIONS = 10000
    
    # Benchmark 1: CircuitBreakerEngine is_tripped latency
    t0 = time.perf_counter_ns()
    for _ in range(ITERATIONS):
        cb_engine.is_tripped("bench")
    t1 = time.perf_counter_ns()
    cb_avg_ns = (t1 - t0) / ITERATIONS
    print(f"1. CircuitBreakerEngine.is_tripped() Avg Latency : {cb_avg_ns:.2f} ns")

    # Benchmark 2: RiskBudgetStore.allocate latency
    reqs = [AllocationRequest(allocation_id=f"a{i}", budget_id="bench", strategy_id="bench", requested_amount=Decimal('1.0')) for i in range(ITERATIONS)]
    t0 = time.perf_counter_ns()
    for req in reqs:
        store.allocate(req)
    t1 = time.perf_counter_ns()
    alloc_avg_ns = (t1 - t0) / ITERATIONS
    print(f"2. RiskBudgetStore.allocate() Avg Latency        : {alloc_avg_ns:.2f} ns")
    
    # Reset store
    store.save(RiskBudget(budget_id="bench", total_capacity=Decimal('1000000.0'), utilized_capacity=Decimal('0.0')))
    
    # Benchmark 3: RiskGuardedCommandBus.dispatch overhead latency
    cmds = [MessageEnvelope.create(ExecuteTradeCommand("AAPL", Decimal('1'), Decimal('1.0'), "bench"), version=1, correlation_id=f"t{i}") for i in range(ITERATIONS)]
    t0 = time.perf_counter_ns()
    for cmd in cmds:
        guarded_bus.dispatch(cmd)
    t1 = time.perf_counter_ns()
    dispatch_avg_ns = (t1 - t0) / ITERATIONS
    print(f"3. RiskGuardedCommandBus.dispatch() Avg Latency  : {dispatch_avg_ns:.2f} ns")

if __name__ == "__main__":
    run_benchmarks()
