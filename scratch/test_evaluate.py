import os
import sys
import pandas as pd
from data.mt5_client import mt5_client
from strategy.evidence_router import EvidenceRouter
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Test")

if not mt5_client.connect():
    logger.error("Failed to connect to MT5")
    sys.exit(1)

evidence_router = EvidenceRouter(os.path.abspath('.'), mode="SHADOW")

for symbol in ["XAUUSD", "EURUSD"]:
    df = mt5_client.get_historical_data(symbol, "M15", 200)
    logger.info(f"Loaded {len(df)} candles for {symbol}")
    if not df.empty:
        signal = evidence_router.evaluate(df, symbol)
        logger.info(f"Signal inside evaluate: {signal}")
