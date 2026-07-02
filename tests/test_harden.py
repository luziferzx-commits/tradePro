import os
import sys


import logging
from unittest.mock import patch, MagicMock

# Force settings before importing modules
import config.settings as settings_module
settings_module.settings.DRY_RUN = True
settings_module.settings.IS_DEMO_ACCOUNT = True
settings_module.settings.MIN_EQUITY = 100.0

from risk.manager import RiskManager
from safety.circuit_breaker import CircuitBreaker
from execution.executor import Executor
from ai.gemini_filter import GeminiFilter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_risk_rounding():
    logger.info("--- Testing Risk Rounding ---")
    
    # Mock MT5 symbol info
    mock_info = MagicMock()
    mock_info.trade_tick_value = 1.0
    mock_info.trade_tick_size = 0.01
    mock_info.point = 0.01
    mock_info.volume_step = 0.05
    mock_info.volume_min = 0.05
    mock_info.volume_max = 50.0
    
    # Mock account info
    mock_account = MagicMock()
    mock_account.balance = 1000.0
    
    with patch('MetaTrader5.symbol_info', return_value=mock_info), \
         patch('MetaTrader5.account_info', return_value=mock_account):
         
         # 1000 balance * 1% risk = 10 risk
         # SL = 500 points. loss_per_lot = (500 * 0.01) * (1.0 / 0.01) = 5 * 100 = 500
         # lots = 10 / 500 = 0.02
         # Round down using step 0.05 -> (0.02 // 0.05) * 0.05 = 0.0
         # Since 0.0 < min_vol (0.05), it should return 0.0 and reject
         vol = RiskManager.calculate_position_size("XAUUSD", 500)
         logger.info(f"Resulting volume for small account: {vol}")
         assert vol == 0.0

def test_circuit_breaker_equity():
    logger.info("--- Testing Circuit Breaker Equity ---")
    mock_account = MagicMock()
    mock_account.equity = 50.0 # Below 100.0 limit
    
    with patch('MetaTrader5.account_info', return_value=mock_account):
        is_safe = CircuitBreaker.check_equity_protection()
        logger.info(f"Is safe to trade with $50 equity? {is_safe}")
        assert is_safe == False

def test_gemini_filter_is_deprecated_noop():
    logger.info("--- Testing GeminiFilter deprecation stub ---")

    # GeminiFilter was removed in V6.1 and replaced by the Quant+ML Consensus
    # Engine. The remaining stub must stay a harmless no-op so legacy references
    # never affect trade decisions.
    gf = GeminiFilter()
    assert gf.filter("anything") is True
    result = gf.analyze({"whatever": 1})
    assert result["approved"] is True
    assert result["confidence"] == 0.0

if __name__ == "__main__":
    test_risk_rounding()
    test_circuit_breaker_equity()
    test_gemini_filter_is_deprecated_noop()
    logger.info("All hardening tests executed successfully.")
