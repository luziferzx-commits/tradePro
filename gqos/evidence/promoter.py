from typing import Optional
from gqos.registry.interfaces import IArtifactRegistry
from gqos.domain.models.evidence import AuditReport, PromotionRecord
from gqos.evidence.events import ArtifactPromotedEvent

class PromotionManager:
    def __init__(self, registry: IArtifactRegistry, bus):
        self.registry = registry
        self.bus = bus

    def promote(self, audit_report: AuditReport, reason: str = "Passed automated lineage audit") -> Optional[PromotionRecord]:
        if not audit_report.is_passed:
            return None
            
        record = PromotionRecord(
            target_artifact_id=audit_report.target_artifact_id,
            audit_report_id=audit_report.artifact_id,
            promotion_reason=reason
        )
        
        # Store the promotion record as evidence
        self.registry.store(record)
        
        # Publish event
        event = ArtifactPromotedEvent(
            promotion_record_id=record.artifact_id,
            target_artifact_id=record.target_artifact_id
        )
        self.bus.publish(event)
        
        return record
