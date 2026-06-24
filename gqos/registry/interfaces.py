from abc import ABC, abstractmethod
from typing import List, Optional
from gqos.domain.interfaces import IArtifact

class IArtifactRegistry(ABC):
    """
    Interface for the unified Artifact Registry.
    """
    
    @abstractmethod
    def store(self, artifact: IArtifact) -> IArtifact:
        """Stores the artifact. If it already exists, returns the existing one idempotently."""
        pass

    @abstractmethod
    def get(self, artifact_id: str) -> Optional[IArtifact]:
        """Retrieves an artifact by its deterministic hash. Raises IntegrityError if corrupted."""
        pass

    @abstractmethod
    def get_lineage(self, artifact_id: str) -> List[IArtifact]:
        """Traverses the parent_ids graph to return the full lineage of the artifact."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Returns the total number of artifacts stored."""
        pass

    @abstractmethod
    def contains(self, artifact_id: str) -> bool:
        """Checks if an artifact exists in the registry."""
        pass
