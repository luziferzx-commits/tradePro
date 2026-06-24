import time
from gqos.state.manager import StateManager

def run_state_benchmark():
    print("--- GQOS State Management Benchmark ---")
    
    manager = StateManager(initial_metadata={"RunID": "bench-run"})
    
    iterations = 100_000
    
    # 1. Snapshot Creation Benchmark
    start_time = time.perf_counter()
    for i in range(iterations):
        manager.apply({f"key": i})
    end_time = time.perf_counter()
    
    avg_creation_us = ((end_time - start_time) / iterations) * 1_000_000
    print(f"Snapshot Creation Time over {iterations} ops: {avg_creation_us:.4f} us per creation")
    assert avg_creation_us < 20.0, f"Snapshot creation time {avg_creation_us:.4f} us exceeds 20 us budget"
    
    # 2. State Read Benchmark
    start_time = time.perf_counter()
    for _ in range(iterations):
        _ = manager.get_snapshot()
    end_time = time.perf_counter()
    
    avg_read_us = ((end_time - start_time) / iterations) * 1_000_000
    print(f"State Read Time over {iterations} ops: {avg_read_us:.4f} us per read")
    assert avg_read_us < 5.0, f"State read time {avg_read_us:.4f} us exceeds 5 us budget"
    
    # 3. Restore Benchmark
    snap_to_restore = manager.get_snapshot()
    start_time = time.perf_counter()
    for _ in range(iterations):
        manager.restore(snap_to_restore)
    end_time = time.perf_counter()
    
    avg_restore_us = ((end_time - start_time) / iterations) * 1_000_000
    print(f"Restore Time over {iterations} ops: {avg_restore_us:.4f} us per restore")
    assert avg_restore_us < 50.0, f"Restore time {avg_restore_us:.4f} us exceeds 50 us budget"
    
    print("--- Benchmark SUCCESS ---")

if __name__ == "__main__":
    run_state_benchmark()
