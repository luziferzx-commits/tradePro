import time
from decimal import Decimal
from gqos.common.enums import TradeDirection
from gqos.sizing.models import SizingRequest, VolatilityMetrics
from gqos.sizing.policies import VolatilityRiskPolicy, VolatilityTargetPolicy
from gqos.sizing.engine import PositionSizingEngine
from gqos.sizing.portfolio import PortfolioSnapshot

def run_benchmark():
    iterations = 1_000_000
    engine = PositionSizingEngine()
    
    # Policy 1: Volatility Risk
    vol_risk_policy = VolatilityRiskPolicy(risk_fraction=Decimal('0.01'), atr_multiplier=Decimal('2.0'))
    
    # Policy 2: Volatility Target
    vol_target_policy = VolatilityTargetPolicy(target_annual_volatility=Decimal('0.15'))
    
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    
    vol = VolatilityMetrics(atr=Decimal('5.0'), annualized_volatility=Decimal('0.30'))
    req = SizingRequest(
        strategy_id="s1",
        symbol="AAPL",
        direction=TradeDirection.BUY,
        entry_price=Decimal('100.0'),
        volatility=vol
    )
    
    print(f"Starting benchmark for {iterations:,} VolatilityRisk calculations...")
    start_time = time.perf_counter()
    for _ in range(iterations):
        engine.size_trade(req, vol_risk_policy, portfolio)
    end_time = time.perf_counter()
    duration_risk = end_time - start_time
    
    print(f"VolatilityRisk Total time: {duration_risk:.4f} seconds")
    print(f"Time per calc: {(duration_risk/iterations)*1e6:.4f} us\n")
    
    print(f"Starting benchmark for {iterations:,} VolatilityTarget calculations...")
    start_time = time.perf_counter()
    for _ in range(iterations):
        engine.size_trade(req, vol_target_policy, portfolio)
    end_time = time.perf_counter()
    duration_target = end_time - start_time
    
    print(f"VolatilityTarget Total time: {duration_target:.4f} seconds")
    print(f"Time per calc: {(duration_target/iterations)*1e6:.4f} us")

if __name__ == "__main__":
    run_benchmark()
