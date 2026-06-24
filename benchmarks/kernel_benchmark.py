import time
from gqos.kernel.di import Kernel, Lifetime
from gqos.kernel.interfaces import IClock
from gqos.kernel.implementations.SystemClock import SystemClock

def run_benchmark():
    print("--- GQOS Kernel Benchmark ---")
    
    # 1. Startup Time Benchmark
    start_time = time.perf_counter()
    Kernel.reset()
    kernel = Kernel.get_instance()
    kernel.register(IClock, lambda: SystemClock(), Lifetime.SINGLETON)
    end_time = time.perf_counter()
    
    startup_ms = (end_time - start_time) * 1000
    print(f"Kernel Startup + Registration Time: {startup_ms:.4f} ms")
    assert startup_ms < 50.0, f"Startup time {startup_ms:.4f} ms exceeds 50 ms budget"
    
    # 2. Resolve Resolution Time (Singleton)
    # Warmup
    _ = kernel.resolve(IClock)
    
    iterations = 1_000_000
    start_time = time.perf_counter()
    for _ in range(iterations):
        _ = kernel.resolve(IClock)
    end_time = time.perf_counter()
    
    total_time_s = end_time - start_time
    avg_resolve_us = (total_time_s / iterations) * 1_000_000
    
    print(f"Resolve Time (Singleton) over {iterations} ops: {avg_resolve_us:.4f} us per resolve")
    assert avg_resolve_us < 5.0, f"Resolve time {avg_resolve_us:.4f} us exceeds 5 us budget"
    
    # 3. Resolve Resolution Time (Transient)
    class Dummy: pass
    kernel.register(Dummy, lambda: Dummy(), Lifetime.TRANSIENT)
    
    start_time = time.perf_counter()
    for _ in range(iterations):
        _ = kernel.resolve(Dummy)
    end_time = time.perf_counter()
    
    total_time_s = end_time - start_time
    avg_transient_us = (total_time_s / iterations) * 1_000_000
    print(f"Resolve Time (Transient) over {iterations} ops: {avg_transient_us:.4f} us per resolve")
    
    print("--- Benchmark SUCCESS ---")

if __name__ == "__main__":
    run_benchmark()
