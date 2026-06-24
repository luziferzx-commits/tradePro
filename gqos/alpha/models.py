from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass
import pandas as pd
import hashlib
import json

from gqos.alpha.manifest import FeatureManifest

@dataclass(frozen=True)
class AlphaMetadata:
    long_only: bool
    supports_short: bool
    supports_leverage: bool
    capacity: str
    estimated_capacity: float  # e.g., max capital in USD before slippage degrades returns
    adv_percentage: float      # limit as % of Average Daily Volume
    liquidity_requirement: str # e.g., "Top 100 S&P", "Binance Top 10"
    expected_holding_period: str
    asset_class: str
    frequency: str
    turnover: str
    expected_market: List[str] # e.g., ["bull", "bear", "sideway", "equity", "crypto"]
    stability_score: float     # e.g., 0.91 from Walk Forward
    tags: List[str]

@dataclass
class ExplanationStore:
    # Maps forecast_id to a dictionary representing the hierarchical explanation
    # e.g., {"id_1": {"Trend": 0.42, "MACD": 0.25, "ADX": 0.17}}
    store: Dict[str, Dict[str, float]]
    
    def get(self, forecast_id: str) -> Optional[Dict[str, float]]:
        return self.store.get(forecast_id)
        
    def add(self, forecast_id: str, explanation: Dict[str, float]):
        self.store[forecast_id] = explanation

@dataclass
class ForecastResult:
    """
    frame columns: ['timestamp', 'score', 'confidence', 'quality', 'horizon', 'half_life', 'forecast_id']
    """
    alpha_id: str
    feature_manifest_hash: str
    frame: pd.DataFrame
    explanations: ExplanationStore

    def calculate_hash(self) -> str:
        # Deterministic hash of the forecast
        data = {
            "alpha_id": self.alpha_id,
            "feature_manifest_hash": self.feature_manifest_hash,
            # For brevity/speed we hash a string representation of the frame shape and sum of scores,
            # In a real system, you would hash the full underlying byte array or parquet buffer.
            "frame_hash": hashlib.sha256(pd.util.hash_pandas_object(self.frame).values).hexdigest(),
            "explanation_keys": sorted(list(self.explanations.store.keys()))
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()

class IAlphaModel(ABC):
    @property
    @abstractmethod
    def alpha_id(self) -> str:
        pass
        
    @property
    @abstractmethod
    def metadata(self) -> AlphaMetadata:
        pass

    @abstractmethod
    def required_features(self) -> List[str]:
        pass

    @abstractmethod
    def generate_forecasts(self, dataset_hash: str, feature_manifest: FeatureManifest, features: Dict[str, pd.Series]) -> ForecastResult:
        """
        Calculates the forecast scores and generates the ForecastResult containing the dataframe and explanation store.
        """
        pass

class AlphaRegistry:
    def __init__(self):
        self._models: Dict[str, IAlphaModel] = {}
        
    def register(self, model: IAlphaModel):
        self._models[model.alpha_id] = model
        
    def get(self, alpha_id: str) -> IAlphaModel:
        return self._models[alpha_id]
        
class IForecastSerializer(ABC):
    @abstractmethod
    def serialize(self, result: ForecastResult, path: str):
        pass
        
    @abstractmethod
    def deserialize(self, path: str) -> ForecastResult:
        pass
