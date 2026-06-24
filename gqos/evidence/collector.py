from typing import List
from gqos.domain.interfaces import IArtifact
from gqos.registry.interfaces import IArtifactRegistry
from gqos.evidence.queue import PendingEvidenceQueue
from gqos.evidence.validator import GraphValidator
from gqos.evidence.events import ValidationFailedEvent
from gqos.domain.models.evidence import EvidencePipelineResult

class EvidenceCollector:
    def __init__(self, registry: IArtifactRegistry, validator: GraphValidator, queue: PendingEvidenceQueue, bus):
        self.registry = registry
        self.validator = validator
        self.queue = queue
        self.bus = bus

    def receive_artifact(self, artifact: IArtifact) -> EvidencePipelineResult:
        """
        Processes an incoming artifact through the evidence pipeline.
        Returns the pipeline result.
        """
        # Process expired items first
        self._process_expired()
        
        # Use iterative approach to prevent recursion depth issues on large graphs
        queue = [artifact]
        primary_result = None
        
        while queue:
            current = queue.pop(0)
            res = self._process_artifact_single(current)
            
            if primary_result is None:
                primary_result = res
                
            if res.status == "STORED":
                resolved = self.queue.parent_resolved(current.artifact_id)
                queue.extend(resolved)
                
        return primary_result
        
    def _process_artifact_single(self, artifact: IArtifact) -> EvidencePipelineResult:
        if self.registry.contains(artifact.artifact_id):
            return EvidencePipelineResult(artifact.artifact_id, "STORED", "Already exists in registry")
            
        validation = self.validator.validate(artifact)
        
        if validation.is_valid:
            self.registry.store(artifact)
            return EvidencePipelineResult(artifact.artifact_id, "STORED", "Passed validation and stored")
        else:
            self.queue.enqueue(artifact, set(validation.missing_parent_ids))
            return EvidencePipelineResult(artifact.artifact_id, "PENDING", f"Missing parents: {validation.missing_parent_ids}")

    def _process_expired(self):
        expired = self.queue.get_expired()
        for art in expired:
            # Publish a failure event for expired artifacts
            val = self.validator.validate(art)
            reason = f"TTL Expired. Still missing: {val.missing_parent_ids}"
            self.bus.publish(ValidationFailedEvent(art.artifact_id, reason))
