from typing import List, Dict
import pandas as pd
import numpy as np

from gqos.alpha.models import IAlphaModel, AlphaMetadata, ForecastResult, ExplanationStore
from gqos.alpha.manifest import FeatureManifest

class BreakoutPack(IAlphaModel):
    def __init__(self, alpha_id: str = "Breakout_Donchian_v1"):
        self._alpha_id = alpha_id
        self._metadata = AlphaMetadata(
            long_only=False,
            supports_short=True,
            supports_leverage=True,
            capacity="HIGH",
            estimated_capacity=20000000.0,
            adv_percentage=0.05,
            liquidity_requirement="Top 1000",
            expected_holding_period="WEEKS_TO_MONTHS",
            asset_class="ANY",
            frequency="DAILY",
            turnover="LOW",
            expected_market=["trend", "bull", "bear"],
            stability_score=0.88,
            tags=["breakout", "donchian"]
        )

    @property
    def alpha_id(self) -> str:
        return self._alpha_id

    @property
    def metadata(self) -> AlphaMetadata:
        return self._metadata

    def required_features(self) -> List[str]:
        # Expecting donchian channel position (0.0 to 1.0)
        return ["donchian_pos"]

    def generate_forecasts(self, dataset_hash: str, feature_manifest: FeatureManifest, features: Dict[str, pd.Series]) -> ForecastResult:
        pos = features["donchian_pos"]
        
        # Breakout Logic
        # if pos == 1.0 -> new high -> +1.0 score
        # if pos == 0.0 -> new low -> -1.0 score
        # Since breakouts decay, we'll apply an exponentially weighted moving average to the pure signals
        # to hold the position open for the trend.
        
        signal = pd.Series(0.0, index=pos.index)
        signal[pos >= 0.99] = 1.0
        signal[pos <= 0.01] = -1.0
        
        # Smooth the signal to hold it (acts like a trailing stop or trend follower)
        score = signal.ewm(span=20, adjust=False).mean()
        
        confidence = pd.Series(0.7, index=score.index)
        quality = pd.Series(1.0, index=score.index)
        
        frame = pd.DataFrame({
            'score': score.fillna(0.0),
            'confidence': confidence,
            'quality': quality,
            'horizon': 20,
            'half_life': 10.0,
            'forecast_id': [f"{self.alpha_id}_{i}" for i in range(len(score))]
        }, index=score.index)
        
        exp_store = ExplanationStore(store={})
        for i, idx in enumerate(frame.index):
            f_id = frame['forecast_id'].iloc[i]
            exp_store.add(f_id, {"donchian_pos": 1.0})
            
        return ForecastResult(
            alpha_id=self.alpha_id,
            feature_manifest_hash=feature_manifest.calculate_hash(),
            frame=frame,
            explanations=exp_store
        )
