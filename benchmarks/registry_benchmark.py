import time
from gqos.registry.in_memory import InMemoryArtifactRegistry
from gqos.domain.models.data import Feature

def run_registry_benchmark():
    print("--- GQOS Registry Benchmark ---")
    
    registry = InMemoryArtifactRegistry()
    iterations = 100_000
    
    # Pre-generate artifacts to strictly measure registry performance
    features = [Feature(f"F{i}", i*0.1, 1000) for i in range(iterations)]
    # Pre-compute hashes to separate hashing time from store time
    for f in features:
        _ = f.artifact_id
    
    # 1. 100k Store
    start = time.perf_counter()
    for feat in features:
        registry.store(feat)
    end = time.perf_counter()
    
    store_us = ((end - start) / iterations) * 1_000_000
    print(f"Store Time: {store_us:.4f} us per artifact")
    assert store_us < 10.0, f"Store time {store_us} exceeds 10us budget"
    
    # 2. 100k Lookup (Integrity Verified)
    start = time.perf_counter()
    for feat in features:
        registry.get(feat.artifact_id)
    end = time.perf_counter()
    
    get_us = ((end - start) / iterations) * 1_000_000
    print(f"Lookup & Integrity Time: {get_us:.4f} us per artifact")
    assert get_us < 15.0, f"Lookup time {get_us} exceeds 15us budget"
    
    # 3. 100k Lineage (Shallow for benchmark purposes, 1 level deep)
    # We create a chain of 100k where each depends on the previous
    # Actually that would be too deep for BFS in Python to do 100k times quickly, 
    # Let's do 10,000 lookups of 10 depth lineage.
    chain = []
    prev_id = features[0].artifact_id
    for i in range(1, 11):
        f = Feature(f"Chain{i}", 1.0, 1000)
        object.__setattr__(f, '_parent_ids', [prev_id])
        registry.store(f)
        chain.append(f)
        prev_id = f.artifact_id
        
    start = time.perf_counter()
    for _ in range(10_000):
        registry.get_lineage(chain[-1].artifact_id)
    end = time.perf_counter()
    
    lineage_us = ((end - start) / 10_000) * 1_000_000
    print(f"10-Depth Lineage Traversal: {lineage_us:.4f} us per traversal")
    
    print("--- Benchmark SUCCESS ---")

if __name__ == "__main__":
    run_registry_benchmark()
