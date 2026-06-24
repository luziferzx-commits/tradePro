from decimal import Decimal
from gqos.common.enums import TradeDirection
from gqos.accounting.models import Position
from gqos.market_data.security_master import MockSecurityMaster
from gqos.risk.analytics.models import FactorExposureResult, FactorReturnAttributionResult, DrawdownAttributionResult
from gqos.risk.analytics.factor_model import MockFactorModel
from gqos.risk.analytics.factor_exposure import FactorExposureEngine
from gqos.risk.analytics.factor_attribution import FactorAttributionEngine
from gqos.risk.analytics.drawdown_attribution import DrawdownAttributionEngine

def test_high_beta_portfolio_exposure():
    # Set up factor model
    mappings = {
        "TSLA": {"Market": Decimal('2.0'), "Momentum": Decimal('1.5')},
        "NVDA": {"Market": Decimal('2.5'), "Momentum": Decimal('2.0')}
    }
    factor_model = MockFactorModel(mappings)
    
    # Portfolio: 50% TSLA, 50% NVDA
    positions = [
        Position("s1", "TSLA", TradeDirection.BUY, Decimal('100.0'), Decimal('10.0')), # 1000
        Position("s1", "NVDA", TradeDirection.BUY, Decimal('10.0'), Decimal('100.0'))  # 1000
    ]
    
    engine = FactorExposureEngine()
    result = engine.calculate_portfolio_exposure(positions, factor_model)
    
    # Market = 0.5 * 2.0 + 0.5 * 2.5 = 1.0 + 1.25 = 2.25
    # Momentum = 0.5 * 1.5 + 0.5 * 2.0 = 0.75 + 1.0 = 1.75
    assert result.exposures["Market"] == Decimal('2.25')
    assert result.exposures["Momentum"] == Decimal('1.75')

def test_unknown_factor_handling():
    factor_model = MockFactorModel({})
    positions = [
        Position("s1", "UNKNOWN", TradeDirection.BUY, Decimal('1.0'), Decimal('100.0'))
    ]
    
    engine = FactorExposureEngine()
    result = engine.calculate_portfolio_exposure(positions, factor_model)
    
    assert result.exposures["UNCLASSIFIED"] == Decimal('1.0')

def test_factor_return_attribution_and_specific_residual():
    # Portfolio has Market Beta = 1.5, Value = 0.5
    portfolio_exposure = FactorExposureResult({
        "Market": Decimal('1.5'),
        "Value": Decimal('0.5')
    })
    
    # Factors returned: Market = +10%, Value = -2%
    factor_returns = {
        "Market": Decimal('0.10'),
        "Value": Decimal('-0.02')
    }
    
    total_portfolio_return = Decimal('0.20') # 20% total return
    
    engine = FactorAttributionEngine()
    result = engine.calculate_attribution(portfolio_exposure, factor_returns, total_portfolio_return)
    
    # Market return contribution = 1.5 * 0.10 = 0.15 (15%)
    # Value return contribution = 0.5 * -0.02 = -0.01 (-1%)
    # Total factor return = 14%
    # Specific (Alpha) = 20% - 14% = +6%
    assert result.factor_returns["Market"] == Decimal('0.15')
    assert result.factor_returns["Value"] == Decimal('-0.01')
    assert result.specific_return == Decimal('0.06')

def test_drawdown_attribution_synthetic_reconciliation():
    # Peak equity:
    # AAPL: 10,000
    # MSFT: 10,000
    # Total = 20,000
    peak_equity = {
        "AAPL": Decimal('10000.0'),
        "MSFT": Decimal('10000.0')
    }
    
    # Trough equity:
    # AAPL: 7,000 (Lost 3,000)
    # MSFT: 9,000 (Lost 1,000)
    # Total = 16,000 (Drawdown = 4,000)
    trough_equity = {
        "AAPL": Decimal('7000.0'),
        "MSFT": Decimal('9000.0')
    }
    
    symbol_to_strategy = {
        "AAPL": "StrategyA",
        "MSFT": "StrategyB"
    }
    
    security_master = MockSecurityMaster({
        "AAPL": "Technology",
        "MSFT": "Technology"
    })
    
    engine = DrawdownAttributionEngine()
    result = engine.calculate_drawdown_attribution(peak_equity, trough_equity, symbol_to_strategy, security_master)
    
    # Total Drawdown
    assert result.total_drawdown_amount == Decimal('4000.0')
    assert result.total_drawdown_percent == Decimal('0.20')
    
    # By Symbol
    assert result.contribution_by_symbol["AAPL"] == Decimal('3000.0')
    assert result.contribution_by_symbol["MSFT"] == Decimal('1000.0')
    
    # By Strategy
    assert result.contribution_by_strategy["StrategyA"] == Decimal('3000.0')
    assert result.contribution_by_strategy["StrategyB"] == Decimal('1000.0')
    
    # By Sector
    assert result.contribution_by_sector["Technology"] == Decimal('4000.0')
    
    # Reconciliation:
    # AAPL (3000) is 75% of 4000
    # MSFT (1000) is 25% of 4000
    assert result.contribution_by_symbol["AAPL"] / result.total_drawdown_amount == Decimal('0.75')
    assert result.contribution_by_symbol["MSFT"] / result.total_drawdown_amount == Decimal('0.25')

def test_deterministic_replay():
    # Replay the drawdown attribution and verify perfectly identical outputs
    peak_equity = {"AAPL": Decimal('10000.0')}
    trough_equity = {"AAPL": Decimal('5000.0')}
    symbol_to_strategy = {"AAPL": "StrategyA"}
    security_master = MockSecurityMaster({"AAPL": "Technology"})
    
    engine = DrawdownAttributionEngine()
    
    res1 = engine.calculate_drawdown_attribution(peak_equity, trough_equity, symbol_to_strategy, security_master)
    res2 = engine.calculate_drawdown_attribution(peak_equity, trough_equity, symbol_to_strategy, security_master)
    
    assert res1.total_drawdown_amount == res2.total_drawdown_amount
    assert res1.contribution_by_sector == res2.contribution_by_sector
    
if __name__ == "__main__":
    test_high_beta_portfolio_exposure()
    test_unknown_factor_handling()
    test_factor_return_attribution_and_specific_residual()
    test_drawdown_attribution_synthetic_reconciliation()
    test_deterministic_replay()
    print("M11C Analytics tests passed!")
