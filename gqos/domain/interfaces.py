from abc import ABC, abstractmethod
from typing import List

class IArtifact(ABC):
    """
    Base interface for all GQOS Domain Objects.
    Guarantees compatibility with the M3 Artifact Registry.
    """
    
    @property
    @abstractmethod
    def artifact_id(self) -> str:
        """
        The globally unique identifier for this artifact.
        Must be a deterministic SHA256 hash of the artifact's content.
        """
        pass
        
    @property
    @abstractmethod
    def parent_ids(self) -> List[str]:
        """
        List of parent artifact IDs that contributed to the creation of this artifact.
        Forms the edges of the Artifact Graph.
        """
        pass

    @property
    def schema_version(self) -> str:
        """
        The version of the artifact schema.
        """
        return "1.0"
