from dataclasses import dataclass, field
from typing import List, Any
from gqos.domain.interfaces import IArtifact
from gqos.domain.utils import generate_deterministic_hash

@dataclass(frozen=True)
class ValidationResult(IArtifact):
    artifact_to_validate_id: str
    is_valid: bool
    missing_parent_ids: List[str]
    errors: List[str]
    _parent_ids: List[str] = field(default_factory=list)
    
    @property
    def artifact_id(self) -> str:
        return generate_deterministic_hash(self)
        
    @property
    def parent_ids(self) -> List[str]:
        # Validations connect to the artifact they validate
        return [self.artifact_to_validate_id] + self._parent_ids
        
    @property
    def schema_version(self) -> str:
        return "1.0"

@dataclass(frozen=True)
class AuditReport(IArtifact):
    target_artifact_id: str
    is_passed: bool
    audited_lineage_ids: List[str]
    audit_notes: str
    _parent_ids: List[str] = field(default_factory=list)
    
    @property
    def artifact_id(self) -> str:
        return generate_deterministic_hash(self)
        
    @property
    def parent_ids(self) -> List[str]:
        return [self.target_artifact_id] + self.audited_lineage_ids + self._parent_ids
        
    @property
    def schema_version(self) -> str:
        return "1.0"

@dataclass(frozen=True)
class PromotionRecord(IArtifact):
    target_artifact_id: str
    audit_report_id: str
    promotion_reason: str
    _parent_ids: List[str] = field(default_factory=list)
    
    @property
    def artifact_id(self) -> str:
        return generate_deterministic_hash(self)
        
    @property
    def parent_ids(self) -> List[str]:
        return [self.target_artifact_id, self.audit_report_id] + self._parent_ids
        
    @property
    def schema_version(self) -> str:
        return "1.0"

@dataclass(frozen=True)
class EvidencePipelineResult(IArtifact):
    target_artifact_id: str
    status: str # "STORED", "PENDING", "FAILED"
    reason: str
    _parent_ids: List[str] = field(default_factory=list)
    
    @property
    def artifact_id(self) -> str:
        return generate_deterministic_hash(self)
        
    @property
    def parent_ids(self) -> List[str]:
        return [self.target_artifact_id] + self._parent_ids
        
    @property
    def schema_version(self) -> str:
        return "1.0"
