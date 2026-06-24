"""tests/test_daily_drawdown_guard.py — Unit tests for DailyDrawdownGuard."""
import pytest
from unittest.mock import patch, MagicMock
from risk.daily_drawdown_guard import DailyDrawdownGuard

# Constants for mocking MT5 deal types
MOCK_DEAL_ENTRY_IN = 0
MOCK_DEAL_ENTRY_OUT = 1


@pytest.fixture
def mock_mt5():
    """Mock the MT5 module used within DailyDrawdownGuard."""
    with patch("risk.daily_drawdown_guard.mt5") as mock:
        mock.DEAL_ENTRY_IN = MOCK_DEAL_ENTRY_IN
        mock.DEAL_ENTRY_OUT = MOCK_DEAL_ENTRY_OUT
        yield mock


@pytest.fixture
def mock_settings():
    """Mock the settings module used within DailyDrawdownGuard."""
    with patch("risk.daily_drawdown_guard.settings") as mock:
        mock.MAX_DAILY_LOSS_PCT = 0.03
        mock.MAX_DAILY_LOSS_WARNING_PCT = 0.02
        yield mock


def make_mock_deal(profit: float, entry_type: int):
    """Helper to create a mocked MT5 deal."""
    deal = MagicMock()
    deal.profit = profit
    deal.entry = entry_type
    return deal


# ── TEST CASES FOR is_safe() ────────────────────────────────────────────────

def test_profitable_day(mock_mt5, mock_settings):
    """1. profitable_day — daily_pnl = +500, expect (True, contains 'profitable')"""
    mock_mt5.account_info.return_value.balance = 100000.0
    mock_mt5.history_deals_get.return_value = [make_mock_deal(500.0, MOCK_DEAL_ENTRY_OUT)]
    
    safe, reason = DailyDrawdownGuard.is_safe()
    assert safe is True
    assert "profitable" in reason.lower()


def test_small_loss_ok(mock_mt5, mock_settings):
    """2. small_loss_ok — daily_pnl = -500, balance=100000 (0.5%), expect (True, 'OK')"""
    mock_mt5.account_info.return_value.balance = 100000.0
    mock_mt5.history_deals_get.return_value = [make_mock_deal(-500.0, MOCK_DEAL_ENTRY_OUT)]
    
    safe, reason = DailyDrawdownGuard.is_safe()
    assert safe is True
    assert "OK" in reason


def test_warning_threshold(mock_mt5, mock_settings):
    """3. warning_threshold — daily_pnl = -2100, balance=100000 (2.1%), expect (True, contains 'WARNING')"""
    mock_mt5.account_info.return_value.balance = 100000.0
    mock_mt5.history_deals_get.return_value = [make_mock_deal(-2100.0, MOCK_DEAL_ENTRY_OUT)]
    
    safe, reason = DailyDrawdownGuard.is_safe()
    assert safe is True
    assert "WARNING" in reason


def test_kill_threshold(mock_mt5, mock_settings):
    """4. kill_threshold — daily_pnl = -3100, balance=100000 (3.1%), expect (False, contains 'DAILY LOSS LIMIT')"""
    mock_mt5.account_info.return_value.balance = 100000.0
    mock_mt5.history_deals_get.return_value = [make_mock_deal(-3100.0, MOCK_DEAL_ENTRY_OUT)]
    
    safe, reason = DailyDrawdownGuard.is_safe()
    assert safe is False
    assert "DAILY LOSS LIMIT" in reason


def test_exactly_at_kill(mock_mt5, mock_settings):
    """5. exactly_at_kill — daily_pnl = -3000, balance=100000 (exactly 3.0%), expect (False, ...)"""
    mock_mt5.account_info.return_value.balance = 100000.0
    mock_mt5.history_deals_get.return_value = [make_mock_deal(-3000.0, MOCK_DEAL_ENTRY_OUT)]
    
    safe, reason = DailyDrawdownGuard.is_safe()
    assert safe is False
    assert "DAILY LOSS LIMIT" in reason


def test_no_deals_today(mock_mt5, mock_settings):
    """6. no_deals_today — history_deals_get returns empty list, expect (True, ...)"""
    mock_mt5.account_info.return_value.balance = 100000.0
    mock_mt5.history_deals_get.return_value = []
    
    safe, reason = DailyDrawdownGuard.is_safe()
    assert safe is True
    assert "OK" in reason or "profitable" in reason.lower()


def test_mt5_returns_none(mock_mt5, mock_settings):
    """7. mt5_returns_none — account_info() returns None, expect (True, 'check_failed...')"""
    mock_mt5.account_info.return_value = None
    
    safe, reason = DailyDrawdownGuard.is_safe()
    assert safe is True
    assert "check_failed" in reason


def test_zero_balance(mock_mt5, mock_settings):
    """8. zero_balance — balance=0, expect (True, 'check_failed_zero_balance')"""
    mock_mt5.account_info.return_value.balance = 0.0
    
    safe, reason = DailyDrawdownGuard.is_safe()
    assert safe is True
    assert "check_failed_zero_balance" in reason


def test_deals_returns_none(mock_mt5, mock_settings):
    """9. deals_returns_none — history_deals_get returns None, expect daily_pnl=0.0, is_safe (True)"""
    mock_mt5.account_info.return_value.balance = 100000.0
    mock_mt5.history_deals_get.return_value = None
    
    safe, reason = DailyDrawdownGuard.is_safe()
    assert safe is True
    assert "OK" in reason or "profitable" in reason.lower()


def test_only_entry_deals(mock_mt5, mock_settings):
    """10. only_entry_deals — deals with entry != DEAL_ENTRY_OUT should be ignored"""
    mock_mt5.account_info.return_value.balance = 100000.0
    mock_mt5.history_deals_get.return_value = [
        make_mock_deal(-5000.0, MOCK_DEAL_ENTRY_IN)  # This large loss should be ignored
    ]
    
    safe, reason = DailyDrawdownGuard.is_safe()
    assert safe is True
    assert "OK" in reason or "profitable" in reason.lower()


# ── TEST CASES FOR get_daily_pnl() ──────────────────────────────────────────

def test_sum_closing_deals(mock_mt5):
    """11. sum_closing_deals — 3 closing deals with profits [100, -300, 50], expect -150.0"""
    mock_mt5.history_deals_get.return_value = [
        make_mock_deal(100.0, MOCK_DEAL_ENTRY_OUT),
        make_mock_deal(-300.0, MOCK_DEAL_ENTRY_OUT),
        make_mock_deal(50.0, MOCK_DEAL_ENTRY_OUT),
    ]
    
    pnl = DailyDrawdownGuard.get_daily_pnl()
    assert pnl == -150.0


def test_ignore_opening_deals(mock_mt5):
    """12. ignore_opening_deals — mix of entry/exit deals, only sum DEAL_ENTRY_OUT"""
    mock_mt5.history_deals_get.return_value = [
        make_mock_deal(100.0, MOCK_DEAL_ENTRY_OUT),
        make_mock_deal(-500.0, MOCK_DEAL_ENTRY_IN),  # Ignore
        make_mock_deal(200.0, MOCK_DEAL_ENTRY_OUT),
        make_mock_deal(-50.0, MOCK_DEAL_ENTRY_IN),   # Ignore
    ]
    
    pnl = DailyDrawdownGuard.get_daily_pnl()
    assert pnl == 300.0
