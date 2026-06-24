from abc import ABC, abstractmethod
from typing import Dict, Any
from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class RegimeState:
    regime_id: str  # e.g., "BULL_VOLATILE", "RANGE_BOUND"
    probability: float  # e.g., 0.85
    metadata: Dict[str, Any]

class IRegimeClassifier(ABC):
    @property
    @abstractmethod
    def classifier_id(self) -> str:
        pass
        
    @abstractmethod
    def classify(self, data: pd.DataFrame, features: Dict[str, pd.Series]) -> pd.Series:
        """
        Returns a pandas Series containing RegimeState objects for each bar.
        """
        pass
