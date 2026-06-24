import time
from decimal import Decimal
from gqos.common.enums import TradeDirection
from gqos.sizing.models import SizingRequest, StrategyMetrics
from gqos.sizing.policies import KellyPolicy
from gqos.sizing.engine import PositionSizingEngine
from gqos.sizing.portfolio import PortfolioSnapshot

def run_benchmark():
    iterations = 1_000_000
    engine = PositionSizingEngine()
    policy = KellyPolicy(fractional_multiplier=Decimal('0.5'), max_kelly_fraction=None)
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    
    metrics = StrategyMetrics(win_rate=Decimal('0.55'), win_loss_ratio=Decimal('2.0'))
    req = SizingRequest("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), metrics=metrics)
    
    print(f"Starting benchmark for {iterations:,} Kelly sizing calculations...")
    
    start_time = time.perf_counter()
    
    for _ in range(iterations):
        engine.size_trade(req, policy, portfolio)
        
    end_time = time.perf_counter()
    duration = end_time - start_time
    
    print(f"Total time: {duration:.4f} seconds")
    print(f"Time per calc: {(duration/iterations)*1e6:.4f} µs")

if __name__ == "__main__":
    run_benchmark()
