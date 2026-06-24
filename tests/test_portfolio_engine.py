"""tests/test_portfolio_engine.py"""
import pytest
from market.symbol_registry import SymbolRegistry
from market.market_metadata import MarketMetadata
from portfolio.correlation_engine import CorrelationEngine
from portfolio.exposure_manager import ExposureManager
from portfolio.capital_allocator import CapitalAllocator
from portfolio.portfolio_var import PortfolioVaR

@pytest.fixture
def mock_registry():
    class MockReg:
        def get_symbol(self, sym):
            return {"asset_class": "INDICES"} if sym in ["US500", "NAS100", "GER40"] else {"asset_class": "FOREX"}
    return MockReg()

@pytest.fixture
def mock_metadata(mock_registry):
    return MarketMetadata(mock_registry)

@pytest.fixture
def correlation_engine(tmp_path):
    config = tmp_path / "corr.yaml"
    with open(config, "w") as f:
        f.write("""
correlations:
  NAS100_US500: 0.95
  US500_NAS100: 0.95
  EURUSD_USDJPY: -0.65
        """)
    return CorrelationEngine(str(config))

def test_correlation_penalty(correlation_engine):
    open_positions = [{"symbol": "US500", "side": "BUY"}]
    
    mult = correlation_engine.calculate_correlation_penalty("NAS100", "BUY", open_positions)
    assert mult == pytest.approx(0.05, abs=0.01)
    
    mult2 = correlation_engine.calculate_correlation_penalty("NAS100", "SELL", open_positions)
    assert mult2 == 1.0

def test_exposure_limits(mock_metadata):
    exposure = ExposureManager(mock_metadata, max_total_risk_pct=0.03, max_asset_class_risk_pct=0.02)
    
    open_pos = [
        {"symbol": "US500", "risk_amount_pct": 0.01},
        {"symbol": "GER40", "risk_amount_pct": 0.01}
    ]
    
    allowed, _ = exposure.check_exposure_limits("NAS100", 0.01, open_pos)
    assert allowed is False
    
    allowed, _ = exposure.check_exposure_limits("EURUSD", 0.01, open_pos)
    assert allowed is True
    
    allowed, _ = exposure.check_exposure_limits("EURUSD", 0.02, open_pos)
    assert allowed is False

def test_capital_allocator(mock_metadata, correlation_engine):
    exposure = ExposureManager(mock_metadata, max_total_risk_pct=0.03, max_asset_class_risk_pct=0.02)
    allocator = CapitalAllocator(mock_metadata, correlation_engine, exposure, base_risk_pct=0.01)
    
    ranked = [
        {"symbol": "US500", "side": "BUY"},
        {"symbol": "NAS100", "side": "BUY"},
        {"symbol": "EURUSD", "side": "SELL"}
    ]
    
    executions, rejections = allocator.allocate(ranked, open_positions=[])
    
    assert len(executions) == 3
    assert executions[0]["symbol"] == "US500"
    assert executions[0]["risk_amount_pct"] == 0.01
    
    assert executions[1]["symbol"] == "NAS100"
    assert executions[1]["risk_amount_pct"] == pytest.approx(0.0005, abs=0.0001)
    
    assert executions[2]["symbol"] == "EURUSD"
    assert executions[2]["risk_amount_pct"] == 0.01

def test_portfolio_var():
    corr = {"A_B": 0.5, "B_A": 0.5}
    open_pos = [
        {"symbol": "A", "side": "BUY", "risk_amount": 100.0},
        {"symbol": "B", "side": "BUY", "risk_amount": 100.0}
    ]
    
    var = PortfolioVaR.calculate_var(open_pos, corr, confidence_level=0.95)
    assert var == pytest.approx(284.9, rel=0.01)
