import os
import sys
import pandas as pd
from data.mt5_client import mt5_client
from strategy.evidence_router import EvidenceRouter
from strategy.indicators import IndicatorCalculator

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("Test")

mt5_client.connect()
evidence_router = EvidenceRouter(os.path.abspath('.'), mode="SHADOW")

for symbol in ["XAUUSD", "BTCUSD", "EURUSD", "GBPUSD", "NAS100", "US30", "USDJPY", "AUDUSD", "ETHUSD", "SPX500"]:
    df = mt5_client.get_historical_data(symbol, "M15", 250)
    if not df.empty:
        df = IndicatorCalculator.add_indicators(df)
        evidence_signal = evidence_router.evaluate(df, symbol)
        logger.info(f"Signal for {symbol}: {evidence_signal}")
