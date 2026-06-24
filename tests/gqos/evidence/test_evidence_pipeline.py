import unittest
import time
from gqos.registry.in_memory import InMemoryArtifactRegistry
from gqos.evidence.queue import PendingEvidenceQueue
from gqos.evidence.validator import GraphValidator
from gqos.evidence.collector import EvidenceCollector
from gqos.evidence.auditor import LineageAuditor
from gqos.evidence.promoter import PromotionManager
from gqos.domain.models.data import Feature, Dataset
from gqos.domain.models.intelligence import Prediction, Decision
from gqos.domain.models.execution import Trade
from gqos.domain.value_objects import Symbol, Timeframe, Probability, Price, LotSize
from gqos.evidence.events import ArtifactCreatedEvent, ArtifactPromotedEvent, ValidationFailedEvent

class MockBus:
    def __init__(self):
        self.published = []
    def publish(self, event):
        self.published.append(event)

class TestEvidencePipeline(unittest.TestCase):
    def setUp(self):
        self.registry = InMemoryArtifactRegistry()
        self.queue = PendingEvidenceQueue(ttl_seconds=0.1) # Fast TTL for tests
        self.validator = GraphValidator(self.registry)
        self.bus = MockBus()
        self.collector = EvidenceCollector(self.registry, self.validator, self.queue, self.bus)
        self.auditor = LineageAuditor(self.registry)
        self.promoter = PromotionManager(self.registry, self.bus)

        # Artifacts
        self.feat = Feature("RSI", 70.0, 160000)
        self.dataset = Dataset(Symbol("XAUUSD"), Timeframe("H1"), [self.feat])
        self.prediction = Prediction(1, Probability(0.8), self.dataset, "v1")
        self.decision = Decision("ENTER", self.prediction, 160001)
        self.trade = Trade(Symbol("XAUUSD"), Price(1900.0), LotSize(0.1), self.decision, 160002)

    def test_pipeline_success(self):
        # Publish in correct order
        self.assertEqual(self.collector.receive_artifact(self.feat).status, "STORED")
        self.assertEqual(self.collector.receive_artifact(self.dataset).status, "STORED")
        self.assertEqual(self.collector.receive_artifact(self.prediction).status, "STORED")
        self.assertEqual(self.collector.receive_artifact(self.decision).status, "STORED")
        self.assertEqual(self.collector.receive_artifact(self.trade).status, "STORED")

        self.assertEqual(self.registry.count(), 5)
        
        # Audit
        report = self.auditor.audit(self.trade.artifact_id)
        self.assertTrue(report.is_passed)
        self.assertEqual(len(report.audited_lineage_ids), 5)
        
        # Promote
        record = self.promoter.promote(report)
        self.assertIsNotNone(record)
        
        # Check event
        promoted_events = [e for e in self.bus.published if isinstance(e, ArtifactPromotedEvent)]
        self.assertEqual(len(promoted_events), 1)
        self.assertEqual(promoted_events[0].target_artifact_id, self.trade.artifact_id)

    def test_missing_parent_queue_and_retry(self):
        # Store prediction BEFORE dataset
        res = self.collector.receive_artifact(self.prediction)
        self.assertEqual(res.status, "PENDING")
        self.assertEqual(self.registry.count(), 0)
        self.assertEqual(self.queue.count(), 1)
        
        # Store dataset BEFORE feature
        res2 = self.collector.receive_artifact(self.dataset)
        self.assertEqual(res2.status, "PENDING")
        self.assertEqual(self.queue.count(), 2)

        # Now store feature. This should resolve dataset, which then resolves prediction.
        res3 = self.collector.receive_artifact(self.feat)
        self.assertEqual(res3.status, "STORED")
        
        # Check that queue is empty and registry has 3 items
        self.assertEqual(self.queue.count(), 0)
        self.assertEqual(self.registry.count(), 3)
        
    def test_dangling_parent_ttl_fail(self):
        res = self.collector.receive_artifact(self.trade)
        self.assertEqual(res.status, "PENDING")
        self.assertEqual(self.queue.count(), 1)
        
        # Wait for TTL to expire
        time.sleep(0.2)
        
        # Next interaction triggers cleanup
        self.collector._process_expired()
        
        self.assertEqual(self.queue.count(), 0)
        self.assertEqual(self.registry.count(), 0)
        
        failed_events = [e for e in self.bus.published if isinstance(e, ValidationFailedEvent)]
        self.assertEqual(len(failed_events), 1)
        self.assertEqual(failed_events[0].target_artifact_id, self.trade.artifact_id)
        self.assertIn("TTL Expired", failed_events[0].reason)

if __name__ == "__main__":
    unittest.main()
