from typing import List, Dict
import pandas as pd
import numpy as np

from gqos.alpha.models import IAlphaModel, AlphaMetadata, ForecastResult, ExplanationStore
from gqos.alpha.manifest import FeatureManifest

class VolatilityPack(IAlphaModel):
    def __init__(self, alpha_id: str = "Volatility_ATRSqueeze_v1"):
        self._alpha_id = alpha_id
        self._metadata = AlphaMetadata(
            long_only=False,
            supports_short=True,
            supports_leverage=False, # Volatility strategies inherently manage sizing, avoid static leverage
            capacity="MEDIUM",
            estimated_capacity=8000000.0,
            adv_percentage=0.08,
            liquidity_requirement="Top 500",
            expected_holding_period="DAYS_TO_WEEKS",
            asset_class="ANY",
            frequency="DAILY",
            turnover="MEDIUM",
            expected_market=["trend", "breakout"],
            stability_score=0.84,
            tags=["volatility", "atr", "squeeze"]
        )

    @property
    def alpha_id(self) -> str:
        return self._alpha_id

    @property
    def metadata(self) -> AlphaMetadata:
        return self._metadata

    def required_features(self) -> List[str]:
        # Expecting raw ATR and a Moving Average (to determine direction)
        # Also Bollinger Bands %B to detect squeeze (e.g. low bandwidth)
        # For simplicity, we just take ATR Z-Score to detect squeeze/expansion
        return ["atr_zscore", "sma_fast", "sma_slow"]

    def generate_forecasts(self, dataset_hash: str, feature_manifest: FeatureManifest, features: Dict[str, pd.Series]) -> ForecastResult:
        atr_z = features["atr_zscore"]
        sma_fast = features["sma_fast"]
        sma_slow = features["sma_slow"]
        
        # Squeeze logic
        # If ATR was very low (Z < -1.0) and is now expanding (Z > 0), we have an expansion.
        # We'll use a simple proxy: positive slope on ATR Z-score while it's > 0 after being < 0.
        atr_expanding = (atr_z > atr_z.shift(1)) & (atr_z > 0.0)
        
        # Direction determined by SMA cross
        trend_up = sma_fast > sma_slow
        trend_down = sma_fast < sma_slow
        
        score = pd.Series(0.0, index=atr_z.index)
        
        # When volatility is expanding, take a position in the direction of the trend
        score[atr_expanding & trend_up] = 0.8
        score[atr_expanding & trend_down] = -0.8
        
        # Decay the score over time to hold position slightly after volatility peaks
        score = score.ewm(span=5, adjust=False).mean()
        
        confidence = pd.Series(0.6, index=score.index)
        quality = pd.Series(1.0, index=score.index)
        
        frame = pd.DataFrame({
            'score': score.fillna(0.0),
            'confidence': confidence,
            'quality': quality,
            'horizon': 5,
            'half_life': 2.0,
            'forecast_id': [f"{self.alpha_id}_{i}" for i in range(len(score))]
        }, index=score.index)
        
        exp_store = ExplanationStore(store={})
        for i, idx in enumerate(frame.index):
            f_id = frame['forecast_id'].iloc[i]
            s = score.iloc[i]
            if s == 0:
                exp_store.add(f_id, {"atr_zscore": 1.0})
            else:
                exp_store.add(f_id, {"atr_zscore": 0.7, "sma_trend": 0.3})
            
        return ForecastResult(
            alpha_id=self.alpha_id,
            feature_manifest_hash=feature_manifest.calculate_hash(),
            frame=frame,
            explanations=exp_store
        )
