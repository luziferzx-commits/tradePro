"""tests/test_trade_journal.py"""
import os
import csv
import pytest
from journal.trade_journal import TradeJournal

def test_trade_journal_creation_and_append(tmp_path):
    sig_file = tmp_path / "signals.csv"
    trd_file = tmp_path / "trades.csv"
    
    journal = TradeJournal(str(sig_file), str(trd_file))
    
    # Headers should be created
    assert os.path.exists(sig_file)
    assert os.path.exists(trd_file)
    
    with open(sig_file, "r") as f:
        reader = csv.reader(f)
        headers = next(reader)
        assert "timestamp" in headers
        assert "symbol" in headers
        
    # Test append signal
    journal.log_signal({
        "symbol": "XAUUSD",
        "side": "BUY",
        "status": "APPROVED",
        "reason": "OK",
        "model_probability": 0.85
    })
    
    with open(sig_file, "r") as f:
        reader = list(csv.reader(f))
        assert len(reader) == 2 # 1 header + 1 row
        row = reader[1]
        assert "XAUUSD" in row
        assert "APPROVED" in row
        
    # Ensure it appends and doesn't overwrite
    journal.log_signal({"symbol": "BTCUSD"})
    with open(sig_file, "r") as f:
        reader = list(csv.reader(f))
        assert len(reader) == 3 # 1 header + 2 rows
