import pandas as pd
import numpy as np

from typing import Dict, List

from gqos.alpha.features import FeatureMetadata, IFeature, ILabelGenerator, InMemoryCache
from gqos.alpha.store import FeatureStore
from gqos.alpha.exceptions import FeatureDependencyCycleError, MissingFeatureDependencyError

def test_feature_metadata_hash():
    meta1 = FeatureMetadata(lookback=14, lag=0, warmup=15, frequency="1d", version="1.0", author="quant")
    meta2 = FeatureMetadata(lookback=14, lag=0, warmup=15, frequency="1d", version="1.0", author="quant")
    assert meta1.calculate_hash() == meta2.calculate_hash()

# --- MOCK FEATURES FOR DAG ---
class ClosePriceFeature(IFeature):
    @property
    def feature_id(self) -> str: return "ClosePrice"
    @property
    def metadata(self) -> FeatureMetadata: return FeatureMetadata(1, 0, 1, "1d", "1.0", "A")
    def dependencies(self) -> List[str]: return []
    def compute(self, data: pd.DataFrame, deps: Dict[str, pd.Series]) -> pd.Series:
        return data["close"]

class SMAFeature(IFeature):
    @property
    def feature_id(self) -> str: return "SMA"
    @property
    def metadata(self) -> FeatureMetadata: return FeatureMetadata(10, 0, 10, "1d", "1.0", "A")
    def dependencies(self) -> List[str]: return ["ClosePrice"]
    def compute(self, data: pd.DataFrame, deps: Dict[str, pd.Series]) -> pd.Series:
        return deps["ClosePrice"].rolling(10).mean()

class MACDFeature(IFeature):
    @property
    def feature_id(self) -> str: return "MACD"
    @property
    def metadata(self) -> FeatureMetadata: return FeatureMetadata(26, 0, 26, "1d", "1.0", "A")
    def dependencies(self) -> List[str]: return ["SMA"]
    def compute(self, data: pd.DataFrame, deps: Dict[str, pd.Series]) -> pd.Series:
        # Mock MACD logic using SMA for the test
        return deps["SMA"] - deps["SMA"].shift(1)

def test_dag_execution_order_and_cache_hit():
    cache = InMemoryCache()
    f1 = ClosePriceFeature()
    f2 = SMAFeature()
    f3 = MACDFeature()
    
    store = FeatureStore(cache=cache, features=[f3, f1, f2]) # unordered
    
    df = pd.DataFrame({"close": np.arange(100.0)})
    manifest, results = store.compute("ds_hash", df, ["MACD", "ClosePrice"])
    
    assert "ClosePrice" in results
    assert "SMA" in results
    assert "MACD" in results
    
    # Verify values
    assert results["ClosePrice"].iloc[0] == 0.0
    assert results["SMA"].iloc[9] == 4.5  # sum(0..9)/10
    
    # Check that cache was populated
    k1 = store._generate_cache_key("ds_hash", f1)
    k2 = store._generate_cache_key("ds_hash", f2)
    k3 = store._generate_cache_key("ds_hash", f3)
    
    assert cache.get(k1) is not None
    assert cache.get(k2) is not None
    assert cache.get(k3) is not None
    
    # Delete a feature from raw and re-compute to prove cache hit prevents duplicate compute
    class ExplodingSMAFeature(SMAFeature):
        def compute(self, data: pd.DataFrame, deps: Dict[str, pd.Series]) -> pd.Series:
            raise RuntimeError("Should not be called if cached!")
            
    f2_exploding = ExplodingSMAFeature()
    store2 = FeatureStore(cache=cache, features=[f3, f1, f2_exploding])
    # Should safely pull SMA from cache
    store2.compute("ds_hash", df, ["MACD"]) 

class CycleFeatureA(IFeature):
    @property
    def feature_id(self) -> str: return "A"
    @property
    def metadata(self) -> FeatureMetadata: return FeatureMetadata(1, 0, 1, "1d", "1.0", "A")
    def dependencies(self) -> List[str]: return ["B"]
    def compute(self, data, deps): return pd.Series()

class CycleFeatureB(IFeature):
    @property
    def feature_id(self) -> str: return "B"
    @property
    def metadata(self) -> FeatureMetadata: return FeatureMetadata(1, 0, 1, "1d", "1.0", "B")
    def dependencies(self) -> List[str]: return ["A"]
    def compute(self, data, deps): return pd.Series()

def test_circular_dependency():
    store = FeatureStore(InMemoryCache(), [CycleFeatureA(), CycleFeatureB()])
    try:
        store._build_lazy_dag(["A"])
        assert False, "Should raise FeatureDependencyCycleError"
    except FeatureDependencyCycleError:
        pass

def test_missing_dependency():
    store = FeatureStore(InMemoryCache(), [CycleFeatureA()])
    try:
        store._build_lazy_dag(["A"])
        assert False, "Should raise MissingFeatureDependencyError"
    except MissingFeatureDependencyError:
        pass

class ForwardReturnLabel(ILabelGenerator):
    @property
    def label_id(self) -> str: return "Forward1Return"
    def generate(self, data: pd.DataFrame) -> pd.Series:
        return data["close"].shift(-1) / data["close"] - 1

def test_label_generator():
    df = pd.DataFrame({"close": [100.0, 105.0, 102.0]})
    labeler = ForwardReturnLabel()
    labels = labeler.generate(df)
    
    assert np.isclose(labels.iloc[0], 0.05)
    assert np.isclose(labels.iloc[1], -0.0285714)
    assert np.isnan(labels.iloc[2])

def test_raw_input_immutability():
    df = pd.DataFrame({"close": [100.0, 105.0, 102.0]})
    df_copy = df.copy()
    
    class MutatingFeature(IFeature):
        @property
        def feature_id(self) -> str: return "Mutator"
        @property
        def metadata(self) -> FeatureMetadata: return FeatureMetadata(1, 0, 1, "1d", "1.0", "A")
        def dependencies(self) -> List[str]: return []
        def compute(self, data: pd.DataFrame, deps: Dict[str, pd.Series]) -> pd.Series:
            data["close"] = 0  # Attempt mutation
            return data["close"]
            
    store = FeatureStore(InMemoryCache(), [MutatingFeature()])
    store.compute("ds_hash", df, ["Mutator"])
    
    # Original dataframe should remain intact because store uses safe copy
    pd.testing.assert_frame_equal(df, df_copy)

if __name__ == "__main__":
    test_feature_metadata_hash()
    test_dag_execution_order_and_cache_hit()
    test_circular_dependency()
    test_missing_dependency()
    test_label_generator()
    test_raw_input_immutability()
    print("M14A Feature Platform tests passed!")
