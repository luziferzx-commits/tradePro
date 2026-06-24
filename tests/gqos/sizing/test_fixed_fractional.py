from decimal import Decimal
from gqos.common.enums import TradeDirection
from gqos.sizing.models import SizingRequest, RoundingPolicy
from gqos.sizing.policies import FixedFractionalPolicy
from gqos.sizing.engine import PositionSizingEngine
from gqos.sizing.portfolio import PortfolioSnapshot

def test_fixed_fractional_basic():
    policy = FixedFractionalPolicy(fraction=Decimal('0.05'), rounding=RoundingPolicy.ROUND_DOWN) # 5%
    engine = PositionSizingEngine()
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    
    # 100k capital, 5% = 5k. Price = 100 -> Qty = 50
    req = SizingRequest("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'))
    res = engine.size_trade(req, policy, portfolio)
    
    assert res.quantity == Decimal('50')
    assert res.estimated_value == Decimal('5000.0')
    assert res.capital_used == Decimal('5000.0')

def test_fixed_fractional_rounding():
    # 100k capital, 5% = 5k. Price = 300 -> Qty = 16.666...
    policy_down = FixedFractionalPolicy(fraction=Decimal('0.05'), rounding=RoundingPolicy.ROUND_DOWN)
    engine = PositionSizingEngine()
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    
    req = SizingRequest("s1", "AAPL", TradeDirection.BUY, Decimal('300.0'))
    res_down = engine.size_trade(req, policy_down, portfolio)
    
    assert res_down.quantity == Decimal('16')
    assert res_down.estimated_value == Decimal('4800.0')
    
    policy_up = FixedFractionalPolicy(fraction=Decimal('0.05'), rounding=RoundingPolicy.ROUND_UP)
    res_up = engine.size_trade(req, policy_up, portfolio)
    
    assert res_up.quantity == Decimal('17')
    assert res_up.estimated_value == Decimal('5100.0')

def test_fixed_fractional_max_value():
    policy = FixedFractionalPolicy(fraction=Decimal('0.05'), max_position_value=Decimal('2000.0'))
    engine = PositionSizingEngine()
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    
    # 100k capital, 5% = 5k. But max is 2k. Price = 100 -> Qty = 20
    req = SizingRequest("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'))
    res = engine.size_trade(req, policy, portfolio)
    
    assert res.quantity == Decimal('20')
    assert res.estimated_value == Decimal('2000.0')

if __name__ == "__main__":
    test_fixed_fractional_basic()
    test_fixed_fractional_rounding()
    test_fixed_fractional_max_value()
    print("Fixed Fractional tests passed!")
