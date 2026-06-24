from typing import List, Dict
import pandas as pd
import numpy as np

from gqos.alpha.models import IAlphaModel, AlphaMetadata, ForecastResult, ExplanationStore
from gqos.alpha.manifest import FeatureManifest

class MeanReversionPack(IAlphaModel):
    def __init__(self, alpha_id: str = "MeanReversion_RSI_BB_v1"):
        self._alpha_id = alpha_id
        self._metadata = AlphaMetadata(
            long_only=False,
            supports_short=True,
            supports_leverage=True,
            capacity="MEDIUM",
            estimated_capacity=5000000.0,
            adv_percentage=0.10,
            liquidity_requirement="Top 100",
            expected_holding_period="INTRADAY_TO_DAYS",
            asset_class="ANY",
            frequency="ANY",
            turnover="HIGH",
            expected_market=["sideway", "range_bound"],
            stability_score=0.82,
            tags=["mean_reversion", "rsi", "bollinger"]
        )

    @property
    def alpha_id(self) -> str:
        return self._alpha_id

    @property
    def metadata(self) -> AlphaMetadata:
        return self._metadata

    def required_features(self) -> List[str]:
        # Expecting raw RSI (0-100) and Bollinger Bands %B
        return ["rsi", "bb_pct_b"]

    def generate_forecasts(self, dataset_hash: str, feature_manifest: FeatureManifest, features: Dict[str, pd.Series]) -> ForecastResult:
        rsi = features["rsi"]
        pct_b = features["bb_pct_b"]
        
        # Mean Reversion Logic
        # RSI > 70 is overbought -> negative score
        # RSI < 30 is oversold -> positive score
        # Map RSI [0, 100] to [-1, 1] linearly for extremes
        rsi_signal = pd.Series(0.0, index=rsi.index)
        rsi_signal[rsi > 70] = -((rsi[rsi > 70] - 70) / 30.0)
        rsi_signal[rsi < 30] = (30 - rsi[rsi < 30]) / 30.0
        
        # Bollinger Bands %B
        # > 1.0 is above upper band -> short
        # < 0.0 is below lower band -> long
        bb_signal = pd.Series(0.0, index=pct_b.index)
        bb_signal[pct_b > 1.0] = -np.clip(pct_b[pct_b > 1.0] - 1.0, 0, 1)
        bb_signal[pct_b < 0.0] = np.clip(abs(pct_b[pct_b < 0.0]), 0, 1)
        
        # Combine (Weighted 50/50)
        score = (rsi_signal * 0.5) + (bb_signal * 0.5)
        
        # Confidence is higher when both align
        alignment = np.sign(rsi_signal) == np.sign(bb_signal)
        confidence = pd.Series(0.5, index=score.index)
        confidence[alignment & (score != 0)] = 0.9
        
        quality = pd.Series(1.0, index=score.index)
        
        frame = pd.DataFrame({
            'score': score.fillna(0.0),
            'confidence': confidence,
            'quality': quality,
            'horizon': 2,
            'half_life': 1.0,
            'forecast_id': [f"{self.alpha_id}_{i}" for i in range(len(score))]
        }, index=score.index)
        
        # Explanations
        exp_store = ExplanationStore(store={})
        for i, idx in enumerate(frame.index):
            f_id = frame['forecast_id'].iloc[i]
            r_sig = rsi_signal.iloc[i]
            b_sig = bb_signal.iloc[i]
            
            total_abs = abs(r_sig) + abs(b_sig)
            if total_abs == 0:
                exp_store.add(f_id, {"rsi": 0.5, "bb_pct_b": 0.5})
            else:
                exp_store.add(f_id, {
                    "rsi": abs(r_sig) / total_abs,
                    "bb_pct_b": abs(b_sig) / total_abs
                })
            
        return ForecastResult(
            alpha_id=self.alpha_id,
            feature_manifest_hash=feature_manifest.calculate_hash(),
            frame=frame,
            explanations=exp_store
        )
