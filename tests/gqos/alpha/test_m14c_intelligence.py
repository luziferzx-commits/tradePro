import os
import pandas as pd
import numpy as np
import tempfile

from gqos.alpha.manifest import FeatureManifest
from gqos.alpha.models import ForecastResult, ExplanationStore, AlphaMetadata
from gqos.alpha.validation import ForecastValidator, ForecastValidationError
from gqos.alpha.serialization import ParquetForecastSerializer
from gqos.alpha.ensemble import StaticWeightEnsemble
from gqos.alpha.regime import RegimeState, IRegimeClassifier
from gqos.alpha.drift import FeatureDriftDetector

def get_mock_result(score: float, conf: float, qual: float, fid: str, alpha_id: str = "A1", feats=None):
    if feats is None: feats = {"Feat1": score}
    df = pd.DataFrame({
        "timestamp": pd.date_range("2023-01-01", periods=1, freq="h"),
        "score": [score],
        "confidence": [conf],
        "quality": [qual],
        "horizon": ["5d"],
        "half_life": ["1d"],
        "forecast_id": [fid]
    })
    
    exp = ExplanationStore({})
    exp.add(fid, feats)
    
    return ForecastResult(alpha_id, "manifest_hash", df, exp)

def test_validator():
    good = get_mock_result(0.5, 0.9, 0.9, "f1")
    ForecastValidator.validate(good) # Should not raise
    
    bad_score = get_mock_result(1.5, 0.9, 0.9, "f2")
    try:
        ForecastValidator.validate(bad_score)
        assert False
    except ForecastValidationError as e:
        assert "Scores must be between" in str(e)

    bad_conf = get_mock_result(0.5, -0.1, 0.9, "f3")
    try:
        ForecastValidator.validate(bad_conf)
        assert False
    except ForecastValidationError as e:
        assert "Confidence must be between" in str(e)

def test_parquet_serialization():
    res = get_mock_result(0.5, 0.9, 0.9, "f1")
    serializer = ParquetForecastSerializer()
    
    with tempfile.TemporaryDirectory() as td:
        serializer.serialize(res, td)
        
        assert os.path.exists(os.path.join(td, "frame.parquet"))
        assert os.path.exists(os.path.join(td, "explanations.json"))
        assert os.path.exists(os.path.join(td, "meta.json"))
        
        loaded = serializer.deserialize(td)
        assert loaded.alpha_id == res.alpha_id
        assert loaded.feature_manifest_hash == res.feature_manifest_hash
        pd.testing.assert_frame_equal(loaded.frame, res.frame)
        assert loaded.explanations.get("f1") == res.explanations.get("f1")

def test_static_weight_ensemble():
    res1 = get_mock_result(0.8, 0.9, 0.8, "f1", "ModelA", {"MACD": 0.5})
    res2 = get_mock_result(-0.2, 0.7, 0.6, "f2", "ModelB", {"RSI": -0.2})
    
    ensemble = StaticWeightEnsemble({"ModelA": 0.6, "ModelB": 0.4})
    
    blended = ensemble.blend({
        "ModelA": res1,
        "ModelB": res2
    })
    
    df = blended.frame
    # score = (0.8 * 0.6) + (-0.2 * 0.4) = 0.48 - 0.08 = 0.40
    assert np.isclose(df["score"].iloc[0], 0.40)
    
    # confidence = (0.9 * 0.6 + 0.7 * 0.4) / 1.0 = 0.54 + 0.28 = 0.82
    assert np.isclose(df["confidence"].iloc[0], 0.82)
    
    # quality = min(0.8, 0.6) = 0.6
    assert np.isclose(df["quality"].iloc[0], 0.6)
    
    # Hierarchical explanation
    fid = df["forecast_id"].iloc[0]
    exp = blended.explanations.get(fid)
    
    assert exp is not None
    # Model level
    assert np.isclose(exp["Model_ModelA"], 0.48)
    assert np.isclose(exp["Model_ModelB"], -0.08)
    
    # Feature level
    assert np.isclose(exp["Feature_MACD"], 0.30) # 0.5 * 0.6
    assert np.isclose(exp["Feature_RSI"], -0.08) # -0.2 * 0.4

def test_feature_drift_detector():
    # Baseline normal mean ~ 0
    np.random.seed(42)
    baseline = pd.Series(np.random.normal(0, 1, 100))
    # OOS shifted mean ~ 2
    oos = pd.Series(np.random.normal(2, 1, 100))
    
    detector = FeatureDriftDetector(p_value_threshold=0.05)
    
    # Should not halt execution
    detector.detect_mean_shift("MACD", baseline, oos)
    
    events = detector.get_events()
    assert len(events) == 1
    assert events[0].feature_id == "MACD"
    assert events[0].metric_name == "MeanShift"
    assert "shifted to OOS mean" in events[0].message

class MockRegimeClassifier(IRegimeClassifier):
    @property
    def classifier_id(self) -> str: return "MockRegime"
    def classify(self, data, features):
        return pd.Series([RegimeState("BULL", 0.9, {})] * len(data))

def test_regime_interface():
    clf = MockRegimeClassifier()
    res = clf.classify(pd.DataFrame({"close": [1,2,3]}), {})
    assert len(res) == 3
    assert res.iloc[0].regime_id == "BULL"

if __name__ == "__main__":
    test_validator()
    test_parquet_serialization()
    test_static_weight_ensemble()
    test_feature_drift_detector()
    test_regime_interface()
    print("M14C Research Intelligence tests passed!")
