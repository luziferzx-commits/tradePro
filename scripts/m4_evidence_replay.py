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

class ConsoleBus:
    def publish(self, event):
        target = getattr(event, 'target_artifact_id', '')
        reason = getattr(event, 'reason', '')
        print(f"[EVENT] {event.__class__.__name__} | Target: {target} | {reason}")

def run_replay():
    print("=== M4 Evidence Pipeline Replay ===\n")
    registry = InMemoryArtifactRegistry()
    queue = PendingEvidenceQueue(ttl_seconds=5.0)
    validator = GraphValidator(registry)
    bus = ConsoleBus()
    collector = EvidenceCollector(registry, validator, queue, bus)
    auditor = LineageAuditor(registry)
    promoter = PromotionManager(registry, bus)

    # Generate full chain of evidence
    feat = Feature("EMA", 120.5, 1000)
    dataset = Dataset(Symbol("BTCUSD"), Timeframe("M15"), [feat])
    pred = Prediction(1, Probability(0.85), dataset, "v2")
    decision = Decision("BUY", pred, 1001)
    trade = Trade(Symbol("BTCUSD"), Price(40000.0), LotSize(1.0), decision, 1002)

    artifacts = [trade, decision, pred, dataset, feat]
    
    print("--- Scenario 1: Out-of-Order Arrival (Simulating network delay) ---")
    print("Publishing artifacts in REVERSE order (Trade -> Feature)\n")
    
    for art in artifacts:
        res = collector.receive_artifact(art)
        print(f"Received {art.__class__.__name__} ({art.artifact_id[:8]}) -> {res.status}")
        
    print(f"\nFinal Registry Count: {registry.count()} / 5 expected")
    print(f"Final Queue Count: {queue.count()} / 0 expected")
    
    print("\n--- Scenario 2: Cryptographic Audit ---")
    report = auditor.audit(trade.artifact_id)
    print(f"Audit Passed? {report.is_passed}")
    print(f"Auditor Notes: {report.audit_notes}")
    
    print("\n--- Scenario 3: Evidence Promotion ---")
    record = promoter.promote(report)
    print(f"Promotion Record Created: {record.artifact_id[:8]}")
    print("Pipeline Execution Completed.")

if __name__ == "__main__":
    run_replay()
