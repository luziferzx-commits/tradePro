from gqos.common.enums import TradeDirection
import unittest
from gqos.messaging.bus import LocalCommandBus, LocalEventBus
from gqos.messaging.store import InMemoryEventStore
from gqos.evidence.queue import PendingEvidenceQueue
from gqos.evidence.validator import GraphValidator
from gqos.registry.in_memory import InMemoryArtifactRegistry
from gqos.evidence.collector import EvidenceCollector
from gqos.execution.engine import ExecutionEngine, ConfigurationError
from gqos.execution.plugins.simulated_broker import SimulatedBrokerPlugin
from gqos.execution.messages import ExecuteTradeCommand, TradeExecutedEvent
from gqos.domain.models.data import Feature, Dataset
from gqos.domain.models.intelligence import Prediction, Decision
from gqos.domain.value_objects import Symbol, Timeframe, Probability
from gqos.messaging.contracts import MessageEnvelope

class DummyLogger:
    def log(self, level, msg):
        pass

class TestExecutionEngine(unittest.TestCase):
    def setUp(self):
        self.logger = DummyLogger()
        self.store = InMemoryEventStore()
        self.command_bus = LocalCommandBus(self.logger, event_store=self.store)
        self.event_bus = LocalEventBus(self.logger, event_store=self.store)
        
        self.registry = InMemoryArtifactRegistry()
        self.queue = PendingEvidenceQueue()
        self.validator = GraphValidator(self.registry)
        self.collector = EvidenceCollector(self.registry, self.validator, self.queue, self.event_bus)
        
        self.engine = ExecutionEngine(self.command_bus, self.event_bus, self.collector)
        self.engine.start()

    def test_plugin_registration_duplicate_fails(self):
        plugin1 = SimulatedBrokerPlugin()
        plugin2 = SimulatedBrokerPlugin()
        
        self.engine.register_plugin(plugin1)
        
        with self.assertRaises(ConfigurationError):
            self.engine.register_plugin(plugin2)

    def test_end_to_end_execution(self):
        self.engine.register_plugin(SimulatedBrokerPlugin())
        
        feat = Feature("EMA", 120.5, 1000)
        dataset = Dataset(Symbol("BTCUSD"), Timeframe("M15"), [feat])
        pred = Prediction(1, Probability(0.85), dataset, "v2")
        decision = Decision("BUY", pred, 1001)
        
        # Pre-store lineage to prevent validation failures
        self.registry.store(feat)
        self.registry.store(dataset)
        self.registry.store(pred)
        self.registry.store(decision)
        
        cmd = ExecuteTradeCommand(decision.symbol, TradeDirection.BUY, decision.quantity, decision.estimated_value, decision.strategy_id)
        env = MessageEnvelope.create(cmd, version=1, correlation_id="c1")
        
        # Dispatch command
        self.command_bus.dispatch(env)
        
        # Check event store
        all_messages = self.store.get_all()
        self.assertEqual(len(all_messages), 2)
        
        self.assertIsInstance(all_messages[0].payload, ExecuteTradeCommand)
        self.assertIsInstance(all_messages[1].payload, TradeExecutedEvent)
        self.assertEqual(all_messages[0].correlation_id, "c1")
        self.assertEqual(all_messages[1].correlation_id, "c1")
        
        # Check registry
        # Trade should be auto-registered by EvidenceCollector intercepting TradeExecutedEvent
        self.assertEqual(self.registry.count(), 5) # 4 pre-stored + 1 trade

if __name__ == "__main__":
    unittest.main()
