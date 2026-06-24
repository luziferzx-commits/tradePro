import pytest
import numpy as np
import pandas as pd
from unittest.mock import MagicMock
from sklearn.tree import DecisionTreeClassifier

from gqos.research.ml.validation import PurgedKFold, get_standard_kfold
from gqos.research.ml.calibration import PlattScaling, IsotonicCalibration
from gqos.research.ml.labels import MetaLabeledAlpha, IMetaMLModel
from gqos.research.ml.explainability import FeatureImportance, SHAPExplainer
from gqos.research.ml.store import ModelStore, MLModelArtifact
from gqos.research.ml.registry import ChampionChallengerRegistry

from gqos.alpha.models import IAlphaModel, AlphaMetadata, ForecastResult, ExplanationStore
from gqos.alpha.manifest import FeatureManifest

# --- Mock Primary Alpha ---
class MockPrimaryAlpha(IAlphaModel):
    @property
    def alpha_id(self) -> str:
        return "primary_1"
        
    @property
    def metadata(self) -> AlphaMetadata:
        return AlphaMetadata(
            long_only=False, supports_short=True, supports_leverage=True,
            capacity="100M", estimated_capacity=100000000.0, adv_percentage=0.1,
            liquidity_requirement="Top 100", expected_holding_period="1d",
            asset_class="equity", frequency="daily", turnover="high",
            expected_market=["bull"], stability_score=0.9, tags=[]
        )

    def required_features(self) -> list:
        return ["feat_1"]

    def generate_forecasts(self, dataset_hash: str, feature_manifest: FeatureManifest, features: dict) -> ForecastResult:
        df = pd.DataFrame({
            "timestamp": [1, 2, 3],
            "score": [0.8, -0.6, 0.0], # Direction: 1, -1, 0
            "confidence": [1.0, 1.0, 1.0],
            "quality": [1.0, 1.0, 1.0],
            "horizon": [1, 1, 1],
            "half_life": [1, 1, 1],
            "forecast_id": ["f1", "f2", "f3"]
        })
        return ForecastResult(self.alpha_id, "hash", df, ExplanationStore({}))

# --- Mock Meta ML Model ---
class MockMetaModel(IMetaMLModel):
    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        # Return probability array [0.9, 0.4, 0.1]
        return np.array([0.9, 0.4, 0.1])

def test_purged_kfold_overlap_and_embargo():
    X = pd.DataFrame(np.random.randn(100, 2))
    y = pd.Series(np.random.randint(0, 2, 100))
    
    cv = PurgedKFold(n_splits=5, purge_pct=0.05, embargo_pct=0.05)
    
    for train_idx, test_idx in cv.split(X, y):
        # Strict non-overlap check
        assert len(np.intersect1d(train_idx, test_idx)) == 0
        
        # Test embargo logic
        if len(train_idx) > 0 and len(test_idx) > 0:
            test_max = test_idx.max()
            right_train = train_idx[train_idx > test_max]
            if len(right_train) > 0:
                assert right_train.min() > test_max + 4 # 5% of 100 is 5, so gap should be at least 5

def test_no_standard_kfold():
    with pytest.raises(NotImplementedError):
        get_standard_kfold()

def test_meta_labeling():
    primary = MockPrimaryAlpha()
    meta = MockMetaModel()
    
    alpha = MetaLabeledAlpha(primary, meta, ["feat_1"])
    
    features = {"feat_1": pd.Series([1.0, 2.0, 3.0])}
    manifest = FeatureManifest(dataset_hash="ds_h", feature_hash="f_h", dependency_hash="d_h", cache_hash="c_h", execution_order=[], engine_version="1")
    
    result = alpha.generate_forecasts("hash", manifest, features)
    df = result.frame
    
    # primary score was [0.8, -0.6, 0.0], direction [1, -1, 0]
    # meta probability was [0.9, 0.4, 0.1]
    # expected final score = direction * probability
    assert df["score"].iloc[0] == pytest.approx(0.9)
    assert df["score"].iloc[1] == pytest.approx(-0.4)
    assert df["score"].iloc[2] == pytest.approx(0.0)
    
    assert df["confidence"].iloc[0] == pytest.approx(0.9)

def test_calibration_interface():
    preds = np.array([0.1, 0.4, 0.6, 0.9])
    y_true = np.array([0, 0, 1, 1])
    
    platt = PlattScaling()
    platt.fit(preds, y_true)
    cal_platt = platt.calibrate(preds)
    assert len(cal_platt) == 4
    
    iso = IsotonicCalibration()
    iso.fit(preds, y_true)
    cal_iso = iso.calibrate(preds)
    assert len(cal_iso) == 4

def test_mda_with_purged_cv():
    X = pd.DataFrame(np.random.randn(100, 3), columns=['A', 'B', 'C'])
    # Make A highly predictive
    y = (X['A'] > 0).astype(int)
    
    model = DecisionTreeClassifier(max_depth=3)
    cv = PurgedKFold(n_splits=3, purge_pct=0.01, embargo_pct=0.01)
    
    importances = FeatureImportance.mean_decrease_accuracy(model, X, y, cv)
    
    assert 'A' in importances.index
    # A should be the most important feature
    assert importances.index[0] == 'A'
    assert importances['A'] > importances['B']

def test_shap_explanation_attach():
    X = pd.DataFrame(np.random.randn(10, 3), columns=['A', 'B', 'C'])
    y = (X['A'] > 0).astype(int)
    
    model = DecisionTreeClassifier(max_depth=3)
    model.fit(X, y)
    
    explainer = SHAPExplainer(model)
    
    primary = MockPrimaryAlpha()
    manifest = FeatureManifest(dataset_hash="ds_h", feature_hash="f_h", dependency_hash="d_h", cache_hash="c_h", execution_order=[], engine_version="1")
    features = {"A": pd.Series(), "B": pd.Series(), "C": pd.Series()}
    # Mocking frame to match X shape
    result = primary.generate_forecasts("hash", manifest, features)
    result.frame = pd.DataFrame({"forecast_id": [f"f{i}" for i in range(10)]})
    
    explained_result = explainer.explain_forecasts(X, result)
    assert len(explained_result.explanations.store) == 10
    assert 'A' in explained_result.explanations.store['f0']

def test_model_store(tmp_path):
    store = ModelStore(base_dir=str(tmp_path))
    model_obj = {"dummy": "model"}
    artifact = MLModelArtifact(model_obj, "mh1", "fh1", "th1")
    
    store.save("alpha_123", artifact)
    
    loaded = store.load("alpha_123")
    assert loaded is not None
    assert loaded.model_hash == "mh1"
    assert loaded.model_obj == {"dummy": "model"}

def test_champion_challenger_registry():
    registry = ChampionChallengerRegistry()
    
    registry.register_challenger("alpha_v2", "strat_1", {"acc": 0.8})
    registry.promote_to_champion("alpha_v2", "Better out of sample performance")
    
    assert registry.get_champion("strat_1") == "alpha_v2"
    assert len(registry.promotion_history) == 1
    assert registry.promotion_history[0]["reason"] == "Better out of sample performance"

if __name__ == "__main__":
    pytest.main(["-v", __file__])
