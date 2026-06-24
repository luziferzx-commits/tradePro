from dataclasses import dataclass
from typing import List
import hashlib
import json
from datetime import datetime, timezone

@dataclass(frozen=True)
class FeatureManifest:
    dataset_hash: str
    feature_hash: str
    dependency_hash: str
    cache_hash: str
    execution_order: List[str]
    engine_version: str
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            object.__setattr__(self, 'created_at', datetime.now(timezone.utc).isoformat())

    def calculate_hash(self) -> str:
        data = {
            "dataset_hash": self.dataset_hash,
            "feature_hash": self.feature_hash,
            "dependency_hash": self.dependency_hash,
            "cache_hash": self.cache_hash,
            "execution_order": self.execution_order,
            "engine_version": self.engine_version,
            "created_at": self.created_at
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()
