from gqos.domain.interfaces import IArtifact
from gqos.registry.interfaces import IArtifactRegistry
from gqos.domain.models.evidence import ValidationResult

class GraphValidator:
    def __init__(self, registry: IArtifactRegistry):
        self.registry = registry

    def validate(self, artifact: IArtifact) -> ValidationResult:
        missing = []
        for pid in artifact.parent_ids:
            if not self.registry.contains(pid):
                missing.append(pid)
                
        is_valid = len(missing) == 0
        errors = [f"Missing parent artifact: {pid}" for pid in missing] if not is_valid else []
        
        return ValidationResult(
            artifact_to_validate_id=artifact.artifact_id,
            is_valid=is_valid,
            missing_parent_ids=missing,
            errors=errors
        )
