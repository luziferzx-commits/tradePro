import time
import threading
from typing import Dict, List, Set
from gqos.domain.interfaces import IArtifact

class PendingEvidenceQueue:
    """
    Holds artifacts that are waiting for their parents to arrive.
    """
    def __init__(self, ttl_seconds: float = 60.0):
        self._queue: Dict[str, dict] = {}
        self.ttl_seconds = ttl_seconds
        self._lock = threading.RLock()

    def enqueue(self, artifact: IArtifact, missing_parents: Set[str]):
        with self._lock:
            if artifact.artifact_id not in self._queue:
                self._queue[artifact.artifact_id] = {
                    "artifact": artifact,
                    "missing": set(missing_parents),
                    "expires": time.time() + self.ttl_seconds
                }

    def parent_resolved(self, parent_id: str) -> List[IArtifact]:
        """
        Called when a new artifact is stored in the registry.
        Checks if any pending artifacts were waiting for it.
        Returns a list of artifacts that are now fully resolved and ready to be validated again.
        """
        resolved_artifacts = []
        with self._lock:
            for aid, item in list(self._queue.items()):
                if parent_id in item["missing"]:
                    item["missing"].remove(parent_id)
                
                if not item["missing"]:
                    resolved_artifacts.append(item["artifact"])
                    del self._queue[aid]
                    
        return resolved_artifacts

    def get_expired(self) -> List[IArtifact]:
        """
        Returns artifacts that have exceeded their TTL.
        """
        now = time.time()
        expired = []
        with self._lock:
            for aid, item in list(self._queue.items()):
                if now > item["expires"]:
                    expired.append(item["artifact"])
                    del self._queue[aid]
        return expired
        
    def count(self) -> int:
        with self._lock:
            return len(self._queue)
