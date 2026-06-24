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
from gqos.observability.metrics import MetricsRegistry, InMemoryMetricsSink
from gqos.observability.tracing import TraceManager, TraceStore
from gqos.observability.health import HealthMonitor, HealthStatus
from gqos.observability.engine import ObservableEventBus, ObservableCommandBus

class DummyHealthCheck:
    def check_health(self) -> HealthStatus:
        return HealthStatus.OK

def run_replay():
    print("=== M6 Observability Platform Replay ===\n")
    
    logger = type("DummyLogger", (), {"log": lambda self, lvl, msg: print(f"[{lvl}] {msg}")})()
    
    # 1. Initialize Telemetry Stores
    metrics_sink = InMemoryMetricsSink()
    metrics = MetricsRegistry(metrics_sink)
    trace_store = TraceStore()
    tracer = TraceManager(trace_store)
    health_monitor = HealthMonitor()
    health_monitor.register("EventStore", DummyHealthCheck())
    
    # 2. Initialize Event Store
    store = InMemoryEventStore()
    
    # 3. Initialize Buses with Store attached and Wrap in Observability Layer
    inner_command_bus = LocalCommandBus(logger, event_store=store)
    inner_event_bus = LocalEventBus(logger, event_store=store)
    
    command_bus = ObservableCommandBus(inner_command_bus, metrics, tracer)
    event_bus = ObservableEventBus(inner_event_bus, metrics, tracer)
    
    # 4. Initialize Evidence Platform
    registry = InMemoryArtifactRegistry()
    queue = PendingEvidenceQueue()
    validator = GraphValidator(registry)
    collector = EvidenceCollector(registry, validator, queue, event_bus)
    
    # 5. Initialize Execution Engine
    engine = ExecutionEngine(command_bus, event_bus, collector)
    engine.start()
    
    # 6. Register Plugins
    print("Registering SimulatedBrokerPlugin...")
    engine.register_plugin(SimulatedBrokerPlugin())
    
    # 7. Setup Evidence Graph (Pre-execution)
    feat = Feature("EMA", 120.5, 1000)
    dataset = Dataset(Symbol("BTCUSD"), Timeframe("M15"), [feat])
    pred = Prediction(1, Probability(0.85), dataset, "v2")
    decision = Decision("BUY", pred, 1001)
    
    registry.store(feat)
    registry.store(dataset)
    registry.store(pred)
    registry.store(decision)
    
    # 8. Execute Command
    print("Dispatching ExecuteTradeCommand with trace tracking...\n")
    cmd = ExecuteTradeCommand(decision.symbol, TradeDirection.BUY, decision.quantity, decision.estimated_value, decision.strategy_id)
    env = MessageEnvelope.create(cmd, version=1, correlation_id="trade_run_002", trace_id="trace_002")
    command_bus.dispatch(env)
    
    # 9. Output Metrics
    print("--- Metrics Summary ---")
    for k, v in metrics_sink.counters.items():
        print(f"Counter | {k}: {v}")
        
    print("\n--- Tracing Summary ---")
    traces = trace_store.get_trace("trace_002")
    for t in traces:
        print(f"Span | {t.name} -> {t.duration_ms:.2f} ms")
        
    print("\n--- Health Summary ---")
    print(f"System Health: {health_monitor.get_system_health().name}")
    
    print("\nReplay Completed successfully.")

if __name__ == "__main__":
    run_replay()
