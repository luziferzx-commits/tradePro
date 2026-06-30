"""tests/conftest.py — Global test configuration and mocks."""
import sys
from unittest.mock import MagicMock

import pytest

# Mock MetaTrader5 before any tests or imports run to prevent OS-level crashes
if "MetaTrader5" not in sys.modules:
    mock_mt5 = MagicMock()
    
    # Mock commonly used constants
    mock_mt5.TIMEFRAME_M1 = 1
    mock_mt5.TIMEFRAME_M5 = 5
    mock_mt5.TIMEFRAME_M15 = 15
    mock_mt5.TIMEFRAME_M30 = 30
    mock_mt5.TIMEFRAME_H1 = 16385
    mock_mt5.TIMEFRAME_H4 = 16388
    mock_mt5.TIMEFRAME_D1 = 16408
    mock_mt5.DEAL_ENTRY_IN = 0
    mock_mt5.DEAL_ENTRY_OUT = 1
    
    sys.modules["MetaTrader5"] = mock_mt5


@pytest.fixture(autouse=True)
def isolate_learning_logs(tmp_path, monkeypatch):
    """Keep tests from appending synthetic events to production learning files."""
    log_dir = tmp_path / "learning"
    monkeypatch.setenv("GQOS_SYSTEM_EVENTS_FILE", str(log_dir / "system_events.jsonl"))
    monkeypatch.setenv("GQOS_SLIPPAGE_LOG_FILE", str(log_dir / "slippage_log.jsonl"))

    slippage_module = sys.modules.get("gqos.execution.slippage_tracker")
    if slippage_module is not None:
        slippage_module.slippage_tracker.log_file = log_dir / "slippage_log.jsonl"
