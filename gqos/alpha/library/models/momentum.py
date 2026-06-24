from typing import List, Dict
import pandas as pd
import numpy as np

from gqos.alpha.models import IAlphaModel, AlphaMetadata, ForecastResult, ExplanationStore
from gqos.alpha.manifest import FeatureManifest

class MomentumPack(IAlphaModel):
    def __init__(self, alpha_id: str = "Momentum_MACD_v1"):
        self._alpha_id = alpha_id
        self._metadata = AlphaMetadata(
            long_only=False,
            supports_short=True,
            supports_leverage=True,
            capacity="HIGH",
            estimated_capacity=10000000.0,
            adv_percentage=0.05,
            liquidity_requirement="Top 500",
            expected_holding_period="DAYS_TO_WEEKS",
            asset_class="ANY",
            frequency="DAILY_OR_INTRADAY",
            turnover="MEDIUM",
            expected_market=["bull", "bear", "trend"],
            stability_score=0.85,
            tags=["momentum", "macd"]
        )

    @property
    def alpha_id(self) -> str:
        return self._alpha_id

    @property
    def metadata(self) -> AlphaMetadata:
        return self._metadata

    def required_features(self) -> List[str]:
        # Expecting the orchestrator to provide a normalized MACD (RollingZScore of MACD)
        return ["macd_zscore"]

    def generate_forecasts(self, dataset_hash: str, feature_manifest: FeatureManifest, features: Dict[str, pd.Series]) -> ForecastResult:
        zscore = features["macd_zscore"]
        
        # Mapping z-score to bounded [-1, 1] using tanh or clipping
        # tanh(x/2) gives a nice smooth bound where z=2 -> ~0.76, z=4 -> ~0.96
        raw_score = np.tanh(zscore / 2.0)
        
        # Fill NaNs with 0
        score = raw_score.fillna(0.0)
        
        confidence = pd.Series(0.8, index=score.index) # Static high confidence for momentum
        quality = pd.Series(1.0, index=score.index)    # Assuming pristine data
        
        # Construct frame
        # Make sure index is named 'timestamp' or we just reset it
        frame = pd.DataFrame({
            'score': score,
            'confidence': confidence,
            'quality': quality,
            'horizon': 5, # Expected 5 bars holding
            'half_life': 2.0,
            'forecast_id': [f"{self.alpha_id}_{i}" for i in range(len(score))]
        }, index=score.index)
        
        # Explanations
        exp_store = ExplanationStore(store={})
        for i, idx in enumerate(frame.index):
            f_id = frame['forecast_id'].iloc[i]
            exp_store.add(f_id, {"macd_zscore": 1.0}) # 100% contribution from MACD
            
        return ForecastResult(
            alpha_id=self.alpha_id,
            feature_manifest_hash=feature_manifest.calculate_hash(),
            frame=frame,
            explanations=exp_store
        )
