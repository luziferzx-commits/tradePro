import pytest
from unittest.mock import patch, MagicMock
from risk.guard import RiskGuard
from config.settings import settings

# A helper to create mock mt5 symbols
def _mock_symbol_info(spread=10, point=0.01, session_deals=True, ask=100.0, bid=99.9, tick_value=1.0, tick_size=0.01, volume_step=0.01, volume_min=0.01, volume_max=100.0):
    m = MagicMock()
    m.spread = spread
    m.point = point
    m.session_deals = session_deals
    m.trade_tick_value = tick_value
    m.trade_tick_size = tick_size
    m.volume_step = volume_step
    m.volume_min = volume_min
    m.volume_max = volume_max
    return m

def _mock_account_info(balance=10000.0, equity=10000.0, trade_mode=0): # 0 is demo
    m = MagicMock()
    m.balance = balance
    m.equity = equity
    m.trade_mode = trade_mode
    return m

@pytest.fixture
def mock_mt5():
    with patch('risk.guard.mt5') as mock:
        mock.terminal_info.return_value = MagicMock(connected=True)
        mock.account_info.return_value = _mock_account_info()
        mock.symbol_info.return_value = _mock_symbol_info()
        mock.symbol_info_tick.return_value = MagicMock(ask=100.0, bid=99.9)
        mock.history_deals_get.return_value = [] # No deals today
        mock.ACCOUNT_TRADE_MODE_DEMO = 0
        mock.DEAL_ENTRY_IN = 0
        
        # Also need to patch mt5 inside portfolio_manager and manager
        with patch('risk.portfolio_manager.mt5', mock), patch('risk.manager.mt5', mock):
            yield mock

@pytest.fixture
def risk_setup(mock_mt5):
    # Reset specific settings to a known state for tests
    settings.REQUIRE_STOP_LOSS = True
    settings.REQUIRE_TAKE_PROFIT = True
    settings.ALLOW_LIVE_TRADING = False
    settings.MIN_EQUITY = 100.0
    settings.MAX_SPREAD_POINTS = 50
    settings.MAX_SLIPPAGE_POINTS = 20
    settings.MAX_TRADES_PER_DAY = 5
    settings.MAX_DAILY_LOSS_PCT = 0.05
    settings.MAX_DRAWDOWN_PCT = 0.15
    settings.RISK_PER_TRADE_PCT = 0.01
    
    # Reset CircuitBreaker consecutive losses
    with patch('safety.circuit_breaker.CircuitBreaker.check_consecutive_losses', return_value=True):
        yield mock_mt5

def test_guard_passes_ideal_conditions(risk_setup):
    res = RiskGuard.evaluate_trade("XAUUSD", "BUY", signal_price=100.0, sl_points=50, tp_points=100, ml_prob=0.8)
    assert res["allowed"] is True
    assert res["guard_that_failed"] is None
    assert res["position_size"] > 0

def test_missing_sl_rejected(risk_setup):
    res = RiskGuard.evaluate_trade("XAUUSD", "BUY", signal_price=100.0, sl_points=0, tp_points=100, ml_prob=0.8)
    assert res["allowed"] is False
    assert res["guard_that_failed"] == "MISSING_SL"

def test_missing_tp_rejected(risk_setup):
    res = RiskGuard.evaluate_trade("XAUUSD", "BUY", signal_price=100.0, sl_points=50, tp_points=0, ml_prob=0.8)
    assert res["allowed"] is False
    assert res["guard_that_failed"] == "MISSING_TP"

def test_live_account_rejected(risk_setup):
    risk_setup.account_info.return_value = _mock_account_info(trade_mode=1) # 1 is live
    res = RiskGuard.evaluate_trade("XAUUSD", "BUY", signal_price=100.0, sl_points=50, tp_points=100, ml_prob=0.8)
    assert res["allowed"] is False
    assert res["guard_that_failed"] == "LIVE_ACCOUNT_RESTRICTION"

def test_max_spread_rejected(risk_setup):
    risk_setup.symbol_info.return_value = _mock_symbol_info(spread=60) # > 50
    res = RiskGuard.evaluate_trade("XAUUSD", "BUY", signal_price=100.0, sl_points=50, tp_points=100, ml_prob=0.8)
    assert res["allowed"] is False
    assert res["guard_that_failed"] == "MAX_SPREAD"

def test_slippage_drift_rejected(risk_setup):
    # Signal was at 100.0, current ask is 100.5. Diff = 0.5. Point = 0.01, so diff is 50 points. > 20.
    risk_setup.symbol_info_tick.return_value = MagicMock(ask=100.5, bid=100.4)
    res = RiskGuard.evaluate_trade("XAUUSD", "BUY", signal_price=100.0, sl_points=50, tp_points=100, ml_prob=0.8)
    assert res["allowed"] is False
    assert res["guard_that_failed"] == "PRICE_DRIFT_EXCEEDED"

def test_max_drawdown_rejected(risk_setup):
    # Balance 10000, Equity 8000. Drawdown = 20% > 15%
    risk_setup.account_info.return_value = _mock_account_info(balance=10000.0, equity=8000.0)
    res = RiskGuard.evaluate_trade("XAUUSD", "BUY", signal_price=100.0, sl_points=50, tp_points=100, ml_prob=0.8)
    assert res["allowed"] is False
    assert res["guard_that_failed"] == "MAX_DRAWDOWN"

def test_max_daily_loss_rejected(risk_setup):
    # We mock deals for today to simulate a big loss
    m_deal1 = MagicMock(magic=settings.MAGIC_NUMBER, profit=-600.0) # -6% loss today
    risk_setup.history_deals_get.return_value = [m_deal1]
    
    res = RiskGuard.evaluate_trade("XAUUSD", "BUY", signal_price=100.0, sl_points=50, tp_points=100, ml_prob=0.8)
    assert res["allowed"] is False
    assert res["guard_that_failed"] == "MAX_DAILY_LOSS"

def test_max_trades_per_day_rejected(risk_setup):
    # Mock 5 entry deals today
    m_deal = MagicMock(magic=settings.MAGIC_NUMBER, entry=0) # 0 is DEAL_ENTRY_IN
    risk_setup.history_deals_get.return_value = [m_deal] * 5
    
    res = RiskGuard.evaluate_trade("XAUUSD", "BUY", signal_price=100.0, sl_points=50, tp_points=100, ml_prob=0.8)
    assert res["allowed"] is False
    assert res["guard_that_failed"] == "MAX_TRADES_PER_DAY"

def test_risk_exceeds_cap(risk_setup):
    # Simulate a scenario where RiskManager calculates a volume that exceeds the strict cap.
    # In reality RiskManager handles it, but if it slips, guard should catch it.
    with patch('risk.manager.RiskManager.calculate_position_size', return_value=100.0): # 100 lots
        res = RiskGuard.evaluate_trade("XAUUSD", "BUY", signal_price=100.0, sl_points=50, tp_points=100, ml_prob=0.8)
        assert res["allowed"] is False
        assert res["guard_that_failed"] == "RISK_EXCEEDS_CAP"
