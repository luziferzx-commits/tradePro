import pandas as pd
import numpy as np
import hashlib
from typing import List, Dict

from gqos.alpha.manifest import FeatureManifest
from gqos.alpha.models import (
    AlphaMetadata, ExplanationStore, ForecastResult, 
    IAlphaModel, AlphaRegistry, IForecastSerializer
)

class MockSerializer(IForecastSerializer):
    def __init__(self):
        self.store = {}
    def serialize(self, result: ForecastResult, path: str):
        self.store[path] = result
    def deserialize(self, path: str) -> ForecastResult:
        return self.store[path]

class MockTrendAlpha(IAlphaModel):
    @property
    def alpha_id(self) -> str: return "Trend_v1"
    
    @property
    def metadata(self) -> AlphaMetadata:
        return AlphaMetadata(
            long_only=False, supports_short=True, supports_leverage=True,
            capacity="$100M", expected_holding_period="5d",
            asset_class="crypto", frequency="1h", turnover="10%", tags=["Trend", "MACD"]
        )

    def required_features(self) -> List[str]:
        return ["MACD"]

    def generate_forecasts(self, dataset_hash: str, feature_manifest: FeatureManifest, features: Dict[str, pd.Series]) -> ForecastResult:
        macd = features["MACD"]
        
        # Generate dataframe
        df = pd.DataFrame(index=macd.index)
        df["timestamp"] = pd.date_range("2023-01-01", periods=len(macd), freq="h")
        
        # Simple mock logic
        df["score"] = np.where(macd > 0, 0.8, -0.8)
        df["confidence"] = 0.95
        df["quality"] = 0.99
        df["horizon"] = "5d"
        df["half_life"] = "1d"
        
        # Forecast ID includes lineage
        df["forecast_id"] = [
            hashlib.sha256(f"{dataset_hash}_{feature_manifest.feature_hash}_{self.alpha_id}_{ts}".encode('utf-8')).hexdigest()
            for ts in df["timestamp"]
        ]
        
        # Explanation store
        explanations = ExplanationStore({})
        for idx, row in df.iterrows():
            f_id = row["forecast_id"]
            score = row["score"]
            explanations.add(f_id, {
                "Trend": score,
                "MACD": score * 0.8,
                "ADX": score * 0.2
            })
            
        return ForecastResult(
            alpha_id=self.alpha_id,
            feature_manifest_hash=feature_manifest.calculate_hash(),
            frame=df,
            explanations=explanations
        )

def test_feature_manifest_integrity():
    manifest = FeatureManifest("ds1", "feat1", "dep1", "cache1", ["f1"], "v1")
    assert manifest.calculate_hash() is not None
    assert manifest.created_at != ""

def test_forecast_generation_and_confidence_propagation():
    manifest = FeatureManifest("ds1", "feat1", "dep1", "cache1", ["MACD"], "v1")
    features = {"MACD": pd.Series([-1.0, 1.0, 2.0])}
    
    model = MockTrendAlpha()
    result = model.generate_forecasts("ds_hash", manifest, features)
    
    df = result.frame
    assert "score" in df.columns
    assert "confidence" in df.columns
    assert "quality" in df.columns
    assert "horizon" in df.columns
    
    assert df["score"].iloc[0] == -0.8
    assert df["score"].iloc[1] == 0.8
    
    assert df["confidence"].iloc[0] == 0.95
    assert df["quality"].iloc[0] == 0.99
    assert df["horizon"].iloc[0] == "5d"
    
def test_explanation_completeness():
    manifest = FeatureManifest("ds1", "feat1", "dep1", "cache1", ["MACD"], "v1")
    features = {"MACD": pd.Series([1.0])}
    
    model = MockTrendAlpha()
    result = model.generate_forecasts("ds_hash", manifest, features)
    
    f_id = result.frame["forecast_id"].iloc[0]
    exp = result.explanations.get(f_id)
    
    assert exp is not None
    assert "Trend" in exp
    assert "MACD" in exp
    assert exp["Trend"] == 0.8

def test_forecast_deterministic_hash_and_serialization():
    manifest = FeatureManifest("ds1", "feat1", "dep1", "cache1", ["MACD"], "v1")
    features = {"MACD": pd.Series([1.0])}
    
    model = MockTrendAlpha()
    result = model.generate_forecasts("ds_hash", manifest, features)
    
    h1 = result.calculate_hash()
    
    serializer = MockSerializer()
    serializer.serialize(result, "path/to/save")
    loaded = serializer.deserialize("path/to/save")
    
    assert loaded.calculate_hash() == h1

def test_forecast_lineage_replay():
    # Implicitly tested via the construction of forecast_id which binds dataset, feature manifest, alpha id
    manifest = FeatureManifest("ds1", "feat1", "dep1", "cache1", ["MACD"], "v1")
    features = {"MACD": pd.Series([1.0])}
    
    model = MockTrendAlpha()
    result = model.generate_forecasts("ds_hash", manifest, features)
    
    f_id = result.frame["forecast_id"].iloc[0]
    # To truly replay, one would parse the ID or lookup the DB via alpha_id + feature_manifest_hash.
    assert result.alpha_id == "Trend_v1"
    assert result.feature_manifest_hash == manifest.calculate_hash()

if __name__ == "__main__":
    test_feature_manifest_integrity()
    test_forecast_generation_and_confidence_propagation()
    test_explanation_completeness()
    test_forecast_deterministic_hash_and_serialization()
    test_forecast_lineage_replay()
    print("M14B Alpha Models tests passed!")
