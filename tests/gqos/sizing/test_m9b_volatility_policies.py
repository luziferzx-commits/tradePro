from decimal import Decimal
from gqos.common.enums import TradeDirection
from gqos.sizing.models import SizingRequest, VolatilityMetrics, InvalidSizingRequestError
from gqos.sizing.portfolio import PortfolioSnapshot
from gqos.sizing.policies import VolatilityRiskPolicy, VolatilityTargetPolicy

def test_volatility_risk_policy_buy_dynamic_stop():
    policy = VolatilityRiskPolicy(risk_fraction=Decimal('0.01'), atr_multiplier=Decimal('2.0'))
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    vol = VolatilityMetrics(atr=Decimal('5.0'))
    
    # Capital = 100,000. Risk = 1,000 (1%).
    # Entry = 100. ATR = 5. Multiplier = 2.
    # Dynamic Stop = 100 - (5 * 2) = 90.
    # Loss per share = 10.
    # Qty = 1000 / 10 = 100 shares.
    
    req = SizingRequest(
        strategy_id="s1",
        symbol="AAPL",
        direction=TradeDirection.BUY,
        entry_price=Decimal('100.0'),
        volatility=vol
    )
    
    result = policy.calculate_size(req, portfolio)
    
    assert result.quantity == Decimal('100')
    assert result.dynamic_stop_loss == Decimal('90.0')
    assert "VolatilityRisk(risk=0.01, atr_mult=2.0)" in result.sizing_reason
    assert "ATR=5.0" in result.sizing_reason

def test_volatility_risk_policy_sell_dynamic_stop():
    policy = VolatilityRiskPolicy(risk_fraction=Decimal('0.01'), atr_multiplier=Decimal('2.0'))
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    vol = VolatilityMetrics(atr=Decimal('5.0'))
    
    # Capital = 100,000. Risk = 1,000.
    # Entry = 100. ATR = 5. Multiplier = 2.
    # Dynamic Stop = 100 + (5 * 2) = 110.
    # Loss per share = 10.
    # Qty = 1000 / 10 = 100 shares.
    
    req = SizingRequest(
        strategy_id="s1",
        symbol="AAPL",
        direction=TradeDirection.SELL,
        entry_price=Decimal('100.0'),
        volatility=vol
    )
    
    result = policy.calculate_size(req, portfolio)
    
    assert result.quantity == Decimal('100')
    assert result.dynamic_stop_loss == Decimal('110.0')

def test_volatility_risk_policy_explicit_stop_overrides_dynamic():
    policy = VolatilityRiskPolicy(risk_fraction=Decimal('0.01'), atr_multiplier=Decimal('2.0'))
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    vol = VolatilityMetrics(atr=Decimal('5.0'))
    
    # Capital = 100,000. Risk = 1,000.
    # Entry = 100. Explicit Stop = 80.
    # Loss per share = 20.
    # Qty = 1000 / 20 = 50 shares.
    
    req = SizingRequest(
        strategy_id="s1",
        symbol="AAPL",
        direction=TradeDirection.BUY,
        entry_price=Decimal('100.0'),
        stop_loss_price=Decimal('80.0'),
        volatility=vol
    )
    
    result = policy.calculate_size(req, portfolio)
    
    assert result.quantity == Decimal('50')
    assert result.dynamic_stop_loss is None # Explicitly not dynamic

def test_volatility_risk_policy_missing_atr_fails():
    policy = VolatilityRiskPolicy(risk_fraction=Decimal('0.01'), atr_multiplier=Decimal('2.0'))
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    
    req = SizingRequest(
        strategy_id="s1",
        symbol="AAPL",
        direction=TradeDirection.BUY,
        entry_price=Decimal('100.0')
    )
    
    try:
        policy.calculate_size(req, portfolio)
    except InvalidSizingRequestError as e:
        assert "VolatilityRiskPolicy requires VolatilityMetrics with ATR" in str(e)
    else:
        assert False, "Expected InvalidSizingRequestError"

def test_volatility_risk_policy_zero_atr_fails():
    policy = VolatilityRiskPolicy(risk_fraction=Decimal('0.01'), atr_multiplier=Decimal('2.0'))
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    vol = VolatilityMetrics(atr=Decimal('0.0'))
    
    req = SizingRequest(
        strategy_id="s1",
        symbol="AAPL",
        direction=TradeDirection.BUY,
        entry_price=Decimal('100.0'),
        volatility=vol
    )
    
    try:
        policy.calculate_size(req, portfolio)
    except InvalidSizingRequestError as e:
        assert "ATR must be > 0" in str(e)
    else:
        assert False, "Expected InvalidSizingRequestError"

def test_volatility_target_policy_sizing():
    policy = VolatilityTargetPolicy(target_annual_volatility=Decimal('0.15')) # Target 15% Vol
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    vol = VolatilityMetrics(atr=Decimal('5.0'), annualized_volatility=Decimal('0.30')) # Asset 30% Vol
    
    # Capital = 100,000
    # Target Vol = 15%. Asset Vol = 30%.
    # Capital Target = 100,000 * (0.15 / 0.30) = 50,000
    # Entry = 100
    # Qty = 50,000 / 100 = 500 shares.
    
    req = SizingRequest(
        strategy_id="s1",
        symbol="AAPL",
        direction=TradeDirection.BUY,
        entry_price=Decimal('100.0'),
        volatility=vol
    )
    
    result = policy.calculate_size(req, portfolio)
    
    assert result.quantity == Decimal('500')
    assert "VolatilityTarget(target_vol=0.15)" in result.sizing_reason
    assert "AssetVol=0.30" in result.sizing_reason

def test_volatility_target_policy_missing_annualized_vol_fails():
    policy = VolatilityTargetPolicy(target_annual_volatility=Decimal('0.15'))
    portfolio = PortfolioSnapshot.create_mock(Decimal('100000.0'))
    vol = VolatilityMetrics(atr=Decimal('5.0')) # Missing annualized_volatility
    
    req = SizingRequest(
        strategy_id="s1",
        symbol="AAPL",
        direction=TradeDirection.BUY,
        entry_price=Decimal('100.0'),
        volatility=vol
    )
    
    try:
        policy.calculate_size(req, portfolio)
    except InvalidSizingRequestError as e:
        assert "VolatilityTargetPolicy requires VolatilityMetrics with annualized_volatility" in str(e)
    else:
        assert False, "Expected InvalidSizingRequestError"

if __name__ == "__main__":
    test_volatility_risk_policy_buy_dynamic_stop()
    test_volatility_risk_policy_sell_dynamic_stop()
    test_volatility_risk_policy_explicit_stop_overrides_dynamic()
    test_volatility_risk_policy_missing_atr_fails()
    test_volatility_risk_policy_zero_atr_fails()
    test_volatility_target_policy_sizing()
    test_volatility_target_policy_missing_annualized_vol_fails()
    print("M9B Volatility Policy tests passed!")
