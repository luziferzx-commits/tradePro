from decimal import Decimal
from gqos.common.enums import TradeDirection
from gqos.sizing.models import SizingRequest, RoundingPolicy, StrategyMetrics, InvalidSizingRequestError
from gqos.sizing.policies import KellyPolicy
from gqos.sizing.engine import PositionSizingEngine
from gqos.sizing.portfolio import PortfolioSnapshot

def test_kelly_policy_full():
    policy = KellyPolicy(fractional_multiplier=Decimal('1.0'), rounding=RoundingPolicy.ROUND_DOWN, max_kelly_fraction=None)
    engine = PositionSizingEngine()
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    
    # W = 0.55, R = 2.0 -> K = 0.55 - (0.45 / 2.0) = 0.55 - 0.225 = 0.325 (32.5% Kelly)
    # 100k * 0.325 = 32.5k target capital
    # Entry = 100 -> Qty = 325
    metrics = StrategyMetrics(win_rate=Decimal('0.55'), win_loss_ratio=Decimal('2.0'))
    req = SizingRequest("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), metrics=metrics)
    res = engine.size_trade(req, policy, portfolio)
    
    assert res.quantity == Decimal('325')
    assert res.estimated_value == Decimal('32500.0')

def test_kelly_policy_half():
    policy = KellyPolicy(fractional_multiplier=Decimal('0.5'), rounding=RoundingPolicy.ROUND_DOWN, max_kelly_fraction=None)
    engine = PositionSizingEngine()
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    
    metrics = StrategyMetrics(win_rate=Decimal('0.55'), win_loss_ratio=Decimal('2.0'))
    req = SizingRequest("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), metrics=metrics)
    res = engine.size_trade(req, policy, portfolio)
    
    # Half Kelly = 0.325 / 2 = 0.1625 -> 16.25k -> Qty 162.5 -> rounded down = 162
    assert res.quantity == Decimal('162')
    assert res.estimated_value == Decimal('16200.0')

def test_kelly_policy_max_fraction():
    # Set max kelly to 0.2
    policy = KellyPolicy(fractional_multiplier=Decimal('1.0'), max_kelly_fraction=Decimal('0.2'))
    engine = PositionSizingEngine()
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    
    # W = 0.55, R = 2.0 -> K = 0.325
    # Adjusted to 0.2 (20k) -> Qty 200
    metrics = StrategyMetrics(win_rate=Decimal('0.55'), win_loss_ratio=Decimal('2.0'))
    req = SizingRequest("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), metrics=metrics)
    res = engine.size_trade(req, policy, portfolio)
    
    assert res.quantity == Decimal('200')

def test_kelly_policy_negative():
    policy = KellyPolicy(fractional_multiplier=Decimal('1.0'))
    engine = PositionSizingEngine()
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    
    # W = 0.3, R = 1.0 -> K = 0.3 - (0.7/1.0) = -0.4 (Negative Kelly)
    metrics = StrategyMetrics(win_rate=Decimal('0.3'), win_loss_ratio=Decimal('1.0'))
    req = SizingRequest("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), metrics=metrics)
    try:
        engine.size_trade(req, policy, portfolio)
        assert False, "Should raise exception for negative Kelly"
    except InvalidSizingRequestError as e:
        assert "negative or zero" in str(e)

if __name__ == "__main__":
    test_kelly_policy_full()
    test_kelly_policy_half()
    test_kelly_policy_max_fraction()
    test_kelly_policy_negative()
    print("Kelly Policy tests passed!")
