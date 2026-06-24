import timeit
from gqos.messaging.store import InMemoryEventStore
from gqos.messaging.bus import LocalCommandBus
from gqos.execution.messages import ExecuteTradeCommand
from gqos.messaging.contracts import MessageEnvelope
from gqos.domain.models.data import Feature, Dataset
from gqos.domain.models.intelligence import Prediction, Decision
from gqos.domain.value_objects import Symbol, Timeframe, Probability

def run_benchmarks():
    print("=== M5 Execution Platform Benchmarks ===")

    store = InMemoryEventStore()
    
    # Pre-generate some items
    feat = Feature("EMA", 120.5, 1000)
    dataset = Dataset(Symbol("BTCUSD"), Timeframe("M15"), [feat])
    pred = Prediction(1, Probability(0.85), dataset, "v2")
    decision = Decision("BUY", pred, 1001)
    
    cmd = ExecuteTradeCommand(decision)
    env = MessageEnvelope.create(cmd, version=1, correlation_id="bm_01")
    
    # 1. EventStore Append Benchmark
    append_time = timeit.timeit(lambda: store.append(env), number=100000)
    print(f"EventStore Append: {append_time / 100000 * 1e6:.2f} us/op")
    
    # 2. EventStore Stream Lookup Benchmark
    # Note: currently linearly scanning
    stream_time = timeit.timeit(lambda: store.get_stream("bm_01"), number=1000)
    print(f"EventStore get_stream (100k items): {stream_time / 1000 * 1e6:.2f} us/op")
    
    # 3. Command Dispatch Benchmark
    logger = type("DummyLogger", (), {"log": lambda self, lvl, msg: None})()
    c_bus = LocalCommandBus(logger)
    c_bus.register_handler(ExecuteTradeCommand, lambda env: None)
    
    dispatch_time = timeit.timeit(lambda: c_bus.dispatch(env), number=100000)
    print(f"CommandBus Dispatch (Empty handler): {dispatch_time / 100000 * 1e6:.2f} us/op")

if __name__ == "__main__":
    run_benchmarks()
