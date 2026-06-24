from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import hashlib
import json
import pandas as pd

@dataclass(frozen=True)
class FeatureMetadata:
    lookback: int
    lag: int
    warmup: int
    frequency: str
    version: str
    author: str
    
    def calculate_hash(self) -> str:
        data = {
            "lookback": self.lookback,
            "lag": self.lag,
            "warmup": self.warmup,
            "frequency": self.frequency,
            "version": self.version,
            "author": self.author
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()

class IFeature(ABC):
    @property
    @abstractmethod
    def feature_id(self) -> str:
        pass
        
    @property
    @abstractmethod
    def metadata(self) -> FeatureMetadata:
        pass
        
    @abstractmethod
    def dependencies(self) -> List[str]:
        """Returns a list of feature_ids that must be computed before this feature."""
        pass
        
    @abstractmethod
    def compute(self, data: pd.DataFrame, computed_dependencies: Dict[str, pd.Series]) -> pd.Series:
        """
        Computes the feature using raw market data and the results of dependent features.
        Must return a pandas Series aligned with the index of `data`.
        """
        pass

class ILabelGenerator(ABC):
    @property
    @abstractmethod
    def label_id(self) -> str:
        pass

    @abstractmethod
    def generate(self, data: pd.DataFrame) -> pd.Series:
        """Generates the target label (e.g. forward return)"""
        pass

class ICache(ABC):
    @abstractmethod
    def get(self, cache_key: str) -> Optional[pd.Series]:
        pass
        
    @abstractmethod
    def set(self, cache_key: str, data: pd.Series) -> None:
        pass

class InMemoryCache(ICache):
    def __init__(self):
        self._store: Dict[str, pd.Series] = {}
        
    def get(self, cache_key: str) -> Optional[pd.Series]:
        # Return a copy to ensure immutability from the caller's side
        if cache_key in self._store:
            return self._store[cache_key].copy()
        return None
        
    def set(self, cache_key: str, data: pd.Series) -> None:
        self._store[cache_key] = data.copy()
