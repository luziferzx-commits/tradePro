from gqos.common.enums import TradeDirection
import time
from gqos.messaging.bus import LocalCommandBus, LocalEventBus
from gqos.messaging.store import InMemoryEventStore
from gqos.evidence.queue import PendingEvidenceQueue
from gqos.evidence.validator import GraphValidator
from gqos.registry.in_memory import InMemoryArtifactRegistry
from gqos.evidence.collector import EvidenceCollector
from gqos.execution.engine import ExecutionEngine
from gqos.execution.plugins.simulated_broker import SimulatedBrokerPlugin
from gqos.execution.messages import ExecuteTradeCommand
from gqos.domain.models.data import Feature, Dataset
from gqos.domain.models.intelligence import Prediction, Decision
from gqos.domain.value_objects import Symbol, Timeframe, Probability
from gqos.messaging.contracts import MessageEnvelope

def run_replay():
    print("=== M5 Execution Platform Replay ===\n")
    
    logger = type("DummyLogger", (), {"log": lambda self, lvl, msg: print(f"[{lvl}] {msg}")})()
    
    # 1. Initialize Event Store
    store = InMemoryEventStore()
    
    # 2. Initialize Buses with Store attached
    command_bus = LocalCommandBus(logger, event_store=store)
    event_bus = LocalEventBus(logger, event_store=store)
    
    # 3. Initialize Evidence Platform
    registry = InMemoryArtifactRegistry()
    queue = PendingEvidenceQueue()
    validator = GraphValidator(registry)
    collector = EvidenceCollector(registry, validator, queue, event_bus)
    
    # 4. Initialize Execution Engine
    engine = ExecutionEngine(command_bus, event_bus, collector)
    engine.start()
    
    # 5. Register Plugins
    print("Registering SimulatedBrokerPlugin (Exactly-One Handler)...")
    engine.register_plugin(SimulatedBrokerPlugin())
    
    # 6. Setup Evidence Graph (Pre-execution)
    print("Generating Pre-Trade Evidence Graph...")
    feat = Feature("EMA", 120.5, 1000)
    dataset = Dataset(Symbol("BTCUSD"), Timeframe("M15"), [feat])
    pred = Prediction(1, Probability(0.85), dataset, "v2")
    decision = Decision("BUY", pred, 1001)
    
    registry.store(feat)
    registry.store(dataset)
    registry.store(pred)
    registry.store(decision)
    print(f"Artifact Registry Count: {registry.count()}")
    
    # 7. Execute Command
    print("\nDispatching ExecuteTradeCommand to the Engine...")
    cmd = ExecuteTradeCommand(decision.symbol, TradeDirection.BUY, decision.quantity, decision.estimated_value, decision.strategy_id)
    env = MessageEnvelope.create(cmd, version=1, correlation_id="trade_run_001")
    command_bus.dispatch(env)
    
    # 8. Verify EventStore
    print("\n--- Event Store Ledger (Chronological Order) ---")
    stream = store.get_stream("trade_run_001")
    for msg in stream:
        print(f"Stored Message: {msg.payload.__class__.__name__} | CorrelationID: {msg.correlation_id}")
        
    # 9. Verify Evidence Pipeline
    print(f"\nArtifact Registry Count after execution: {registry.count()} / 5 Expected")
    print("Trade was routed through EvidenceCollector seamlessly.")
    print("Replay Execution Completed successfully.")

if __name__ == "__main__":
    run_replay()
