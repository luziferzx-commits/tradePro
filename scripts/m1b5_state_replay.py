import time
from gqos.state.manager import StateManager

def run_m1b5_replay_test():
    print("--- GQOS M1B.5: State Replay Determinism Test ---")
    
    manager = StateManager(initial_metadata={"RunID": "replay-test"})
    
    # Generate 100,000 snapshots
    cycles = 100_000
    print(f"Generating {cycles} state snapshots...")
    snapshots = []
    
    start_gen = time.perf_counter()
    for i in range(cycles):
        snap = manager.apply({
            "tick": i,
            "price": 2000.0 + (i * 0.1),
            "indicators": {"ema": 2000.0, "rsi": 50.0 + (i % 20)}
        })
        snapshots.append(snap)
    end_gen = time.perf_counter()
    print(f"Generated {cycles} snapshots in {end_gen - start_gen:.2f} seconds.")
    
    # Now simulate a replay engine rewinding and fast-forwarding randomly
    print("Running Deterministic Replay Drift Test...")
    import random
    random.seed(42) # Deterministic random for reproducibility
    
    # Select 10,000 random jumps
    jumps = 10_000
    
    for _ in range(jumps):
        target_idx = random.randint(0, cycles - 1)
        target_snap = snapshots[target_idx]
        
        # Restore to that snapshot
        manager.restore(target_snap)
        
        # Verify fidelity
        restored = manager.get_snapshot()
        assert restored.version == target_snap.version, "Version drift detected"
        assert restored.data["tick"] == target_idx, "Data drift detected"
        assert restored.data["indicators"]["rsi"] == 50.0 + (target_idx % 20), "Nested data drift detected"
        
    print(f"Successfully performed {jumps} random time-travels with 0% drift.")
    print("--- M1B.5 SUCCESS ---")

if __name__ == "__main__":
    run_m1b5_replay_test()
