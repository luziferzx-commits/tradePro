"""tests/test_portfolio_risk.py"""
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
            return {
                "asset_class": "INDICES" if sym in ["US500", "NAS100", "GER40"] else "FOREX",
                "min_lot": 0.1,
                "lot_step": 0.1,
                "max_lot": 100.0,
                "tick_value": 1.0,
                "typical_spread_points": 20
            }
    return MockReg()

@pytest.fixture
def mock_metadata(mock_registry):
    return MarketMetadata(mock_registry)

@pytest.fixture
def correlation_engine(tmp_path):
    config = tmp_path / "corr.yaml"
    with open(config, "w") as f:
        f.write("correlations:\n  NAS100_US500: 0.95")
    return CorrelationEngine(str(config), metadata=None)

def test_historical_var_cvar():
    returns = [-5.0, -4.0, -3.0, -2.0, -1.0] + [0.5]*95
    open_pos = [{"risk_amount": 10.0}]
    
    result = PortfolioVaR.calculate_var(open_pos, {}, confidence_level=0.95, historical_returns=returns)
    
    assert result["method"] == "HISTORICAL"
    assert result["var"] == 10.0
    assert result["cvar"] == 30.0

def test_parametric_fallback_warning():
    open_pos = [{"risk_amount": 10.0}]
    result = PortfolioVaR.calculate_var(open_pos, {}, confidence_level=0.95, historical_returns=[])
    
    assert result["method"] == "PARAMETRIC"
    assert "PARAMETRIC_FALLBACK_USED" in result["warnings"]

def test_static_correlation_warning(correlation_engine):
    assert "STATIC_CORRELATION_USED" in correlation_engine.warnings
    
def test_min_lot_rejection(mock_metadata, correlation_engine, monkeypatch):
    import risk.portfolio_drawdown_guard
    monkeypatch.setattr(risk.portfolio_drawdown_guard.PortfolioDrawdownGuard, "is_safe", lambda: (True, "OK"))
    
    exposure = ExposureManager(mock_metadata, max_total_risk_pct=0.03, max_asset_class_risk_pct=0.02)
    allocator = CapitalAllocator(mock_metadata, correlation_engine, exposure, base_risk_pct=0.001, account_balance=100.0)
    
    ranked = [{"symbol": "US500", "side": "BUY"}]
    
    executions, rejections = allocator.allocate(ranked, open_positions=[])
    
    assert len(executions) == 0
    assert len(rejections) == 1
    assert "Min lot bump" in rejections[0]['reject_reason']

def test_dd_guard_reject_all(mock_metadata, correlation_engine, monkeypatch):
    import risk.portfolio_drawdown_guard
    monkeypatch.setattr(risk.portfolio_drawdown_guard.PortfolioDrawdownGuard, "is_safe", lambda: (False, "Max Daily Loss Reached"))
    
    exposure = ExposureManager(mock_metadata)
    allocator = CapitalAllocator(mock_metadata, correlation_engine, exposure)
    
    ranked = [{"symbol": "US500", "side": "BUY"}]
    executions, rejections = allocator.allocate(ranked, open_positions=[])
    
    assert len(executions) == 0
    assert len(rejections) == 1
    assert rejections[0]['reject_reason'] == "PORTFOLIO_DD_GUARD_TRIGGERED"
