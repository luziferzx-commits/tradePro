from decimal import Decimal
from gqos.common.enums import TradeDirection
from gqos.sizing.models import SizingRequest, RoundingPolicy, InvalidSizingRequestError
from gqos.sizing.policies import FixedRiskPolicy
from gqos.sizing.engine import PositionSizingEngine
from gqos.sizing.portfolio import PortfolioSnapshot


def test_fixed_risk_basic():
    policy = FixedRiskPolicy(risk_fraction=Decimal('0.01')) # 1% risk
    engine = PositionSizingEngine()
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    
    # 100k capital, 1% risk = 1k risk
    # Long at 100, Stop at 90. Loss per share = 10.
    # Qty = 1000 / 10 = 100
    req = SizingRequest("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('90.0'))
    res = engine.size_trade(req, policy, portfolio)
    
    assert res.quantity == Decimal('100')
    assert res.estimated_value == Decimal('10000.0')
    assert res.risk_amount == Decimal('1000.0')

def test_fixed_risk_short():
    policy = FixedRiskPolicy(risk_fraction=Decimal('0.01'))
    engine = PositionSizingEngine()
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    
    # Short at 100, Stop at 110. Loss per share = 10.
    req = SizingRequest("s1", "AAPL", TradeDirection.SELL, Decimal('100.0'), Decimal('110.0'))
    res = engine.size_trade(req, policy, portfolio)
    
    assert res.quantity == Decimal('100') # Absolute quantity returned

def test_fixed_risk_validations():
    policy = FixedRiskPolicy(risk_fraction=Decimal('0.01'))
    engine = PositionSizingEngine()
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    
    # 1. No stop loss
    req1 = SizingRequest("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'))
    try:
        engine.size_trade(req1, policy, portfolio)
        assert False, "Should have raised exception"
    except Exception as e:
        assert "requires a stop_loss_price" in str(e)
    
    # 2. Zero stop loss diff
    req2 = SizingRequest("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('100.0'))
    try:
        engine.size_trade(req2, policy, portfolio)
        assert False, "Should have raised exception"
    except Exception as e:
        assert "cannot be identical" in str(e)
    
    # 3. Stop loss above entry for BUY
    req3 = SizingRequest("s1", "AAPL", TradeDirection.BUY, Decimal('100.0'), Decimal('110.0'))
    try:
        engine.size_trade(req3, policy, portfolio)
        assert False, "Should have raised exception"
    except Exception as e:
        assert "must be below entry_price" in str(e)

if __name__ == "__main__":
    test_fixed_risk_basic()
    test_fixed_risk_short()
    test_fixed_risk_validations()
    print("Fixed Risk tests passed!")
