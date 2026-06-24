import time
from decimal import Decimal
from gqos.common.enums import TradeDirection
from gqos.sizing.models import SizingRequest, RoundingPolicy
from gqos.sizing.policies import FixedFractionalPolicy
from gqos.sizing.engine import PositionSizingEngine

def run_benchmark():
    print("=== M8 Position Sizing Engine Benchmark ===")
    
    engine = PositionSizingEngine()
    policy = FixedFractionalPolicy(fraction=Decimal('0.05'), rounding=RoundingPolicy.ROUND_DOWN)
    capital = Decimal('1000000.0') # $1M
    
    req = SizingRequest("s1", "AAPL", TradeDirection.BUY, Decimal('150.0'))
    
    print("\nRunning 1,000,000 size_trade() calculations...")
    
    t0 = time.perf_counter_ns()
    
    # Run 1M times
    for _ in range(1000000):
        engine.size_trade(req, policy, capital)
        
    t1 = time.perf_counter_ns()
    
    total_time_s = (t1 - t0) / 1_000_000_000.0
    latency_us = ((t1 - t0) / 1000000) / 1000.0
    
    print(f"Total Time : {total_time_s:.4f} sec")
    print(f"Avg Latency: {latency_us:.2f} us")
    
if __name__ == "__main__":
    run_benchmark()
