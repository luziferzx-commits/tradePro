from typing import List, Dict, Optional
from gqos.domain.interfaces import IArtifact
from gqos.registry.interfaces import IArtifactRegistry

class IntegrityError(Exception):
    pass

class CycleDetectedError(Exception):
    pass

import threading

class InMemoryArtifactRegistry(IArtifactRegistry):
    def __init__(self):
        self._store: Dict[str, IArtifact] = {}
        self._lock = threading.RLock()

    def store(self, artifact: IArtifact) -> IArtifact:
        with self._lock:
            if artifact.artifact_id in self._store:
                return self._store[artifact.artifact_id] # Idempotent return
            
        # Verify integrity before storing by forcing a manual re-compute of the hash
        from gqos.domain.utils import generate_deterministic_hash
        expected_hash = generate_deterministic_hash(artifact, force_compute=True)
        if expected_hash != artifact.artifact_id:
            raise IntegrityError(f"Artifact ID computation failed. Expected {expected_hash}, got {artifact.artifact_id}")
            
        with self._lock:
            self._store[artifact.artifact_id] = artifact
            return artifact

    def get(self, artifact_id: str) -> Optional[IArtifact]:
        with self._lock:
            artifact = self._store.get(artifact_id)
            if not artifact:
                return None
                
            # Re-compute hash to verify integrity of stored object
            from gqos.domain.utils import generate_deterministic_hash
            computed_id = generate_deterministic_hash(artifact, force_compute=True)
            if computed_id != artifact_id:
                raise IntegrityError(f"Artifact {artifact_id} is corrupted! Hash mismatched: {computed_id}")
                
            return artifact

    def get_lineage(self, artifact_id: str) -> List[IArtifact]:
        """DFS traversal to get the complete lineage graph and detect cycles"""
        with self._lock:
            if artifact_id not in self._store:
                return []
                
            lineage = []
            visited = set()
            
            def dfs(curr_id, path):
                if curr_id in path:
                    raise CycleDetectedError(f"Cycle detected in Artifact Graph at {curr_id}")
                if curr_id in visited:
                    return
                    
                visited.add(curr_id)
                curr_art = self.get(curr_id)
                if curr_art:
                    lineage.append(curr_art)
                    path.add(curr_id)
                    for pid in sorted(curr_art.parent_ids):
                        dfs(pid, path)
                    path.remove(curr_id)
                    
            dfs(artifact_id, set())
            return lineage

    def count(self) -> int:
        with self._lock:
            return len(self._store)

    def contains(self, artifact_id: str) -> bool:
        with self._lock:
            return artifact_id in self._store
