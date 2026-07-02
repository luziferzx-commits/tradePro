"""tests/test_trade_history_loader.py"""
import os
import pandas as pd
import numpy as np
from risk.trade_history_loader import TradeHistoryLoader

def test_generate_synthetic_fallback():
    df = TradeHistoryLoader._generate_synthetic_fallback()
    assert len(df) == 500
    assert 'r_multiple' in df.columns
    assert 'source_file' in df.columns
    assert df['source_file'].iloc[0] == 'SYNTHETIC_FALLBACK'
    
def test_normalize_with_r_col():
    raw = pd.DataFrame({
        'pnl': [1.5, -1.0, 25.0, -30.0, np.nan],
        'symbol': ['XAUUSD', 'BTCUSD', 'EURUSD', 'GBPUSD', 'XYZ']
    })
    
    norm = TradeHistoryLoader._normalize(raw, "dummy.csv", r_col='pnl')
    assert len(norm) == 4 # NaN dropped
    assert 'r_multiple' in norm.columns
    assert norm['r_multiple'].iloc[0] == 1.5
    # Check outlier clipping
    assert norm['r_multiple'].iloc[2] == 20.0
    assert norm['r_multiple'].iloc[3] == -20.0

def test_normalize_with_label_col():
    raw = pd.DataFrame({
        'label': [1, 0, 1, 0, np.nan]
    })
    norm = TradeHistoryLoader._normalize(raw, "dummy.csv", label_col='label')
    assert len(norm) == 4
    assert norm['r_multiple'].iloc[0] == 1.0
    assert norm['r_multiple'].iloc[1] == -1.0
