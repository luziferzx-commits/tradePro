import time
from gqos.domain.value_objects import Symbol, Timeframe
from gqos.domain.models.data import Feature, Dataset

def run_domain_benchmark():
    print("--- GQOS Domain Benchmark ---")
    
    # 1. Feature Creation (Value Object instantiation and hashing)
    iterations = 100_000
    features = []
    
    start_time = time.perf_counter()
    for i in range(iterations):
        feat = Feature(name=f"Feat_{i}", value=i*0.1, timestamp=1600000+i)
        features.append(feat)
    end_time = time.perf_counter()
    
    feat_us = ((end_time - start_time) / iterations) * 1_000_000
    print(f"Feature Creation & Hashing Time: {feat_us:.4f} us per object")
    
    # We want this under 20us ideally
    assert feat_us < 20.0, f"Creation time {feat_us:.4f} exceeds 20us budget"
    
    # 2. Complex Graph Creation
    sym = Symbol("XAUUSD")
    tf = Timeframe("H1")
    
    start_time = time.perf_counter()
    for i in range(1000): # Smaller loop for complex objects
        ds = Dataset(sym, tf, [features[i]])
        # Force the hash property to compute
        hash_id = ds.artifact_id
    end_time = time.perf_counter()
    
    ds_us = ((end_time - start_time) / 1000) * 1_000_000
    print(f"Dataset Creation & Hashing Time: {ds_us:.4f} us per object")
    
    print("--- Benchmark SUCCESS ---")

if __name__ == "__main__":
    run_domain_benchmark()
