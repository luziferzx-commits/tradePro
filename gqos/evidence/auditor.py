from gqos.registry.interfaces import IArtifactRegistry
from gqos.domain.models.evidence import AuditReport
from gqos.registry.in_memory import IntegrityError, CycleDetectedError

class LineageAuditor:
    def __init__(self, registry: IArtifactRegistry):
        self.registry = registry

    def audit(self, target_artifact_id: str) -> AuditReport:
        try:
            lineage = self.registry.get_lineage(target_artifact_id)
            if not lineage:
                return AuditReport(
                    target_artifact_id=target_artifact_id,
                    is_passed=False,
                    audited_lineage_ids=[],
                    audit_notes="Artifact not found in registry"
                )
                
            # Lineage includes the target artifact itself
            lineage_ids = [art.artifact_id for art in lineage]
            return AuditReport(
                target_artifact_id=target_artifact_id,
                is_passed=True,
                audited_lineage_ids=lineage_ids,
                audit_notes=f"Cryptographic lineage verified. Depth: {len(lineage)}"
            )
        except IntegrityError as e:
            return AuditReport(
                target_artifact_id=target_artifact_id,
                is_passed=False,
                audited_lineage_ids=[],
                audit_notes=f"Integrity check failed during traversal: {str(e)}"
            )
        except CycleDetectedError as e:
            return AuditReport(
                target_artifact_id=target_artifact_id,
                is_passed=False,
                audited_lineage_ids=[],
                audit_notes=f"Cycle detected in lineage graph: {str(e)}"
            )
        except Exception as e:
            return AuditReport(
                target_artifact_id=target_artifact_id,
                is_passed=False,
                audited_lineage_ids=[],
                audit_notes=f"Unknown error during audit: {str(e)}"
            )
