import MetaTrader5 as mt5
import yaml
import logging

logging.basicConfig(level=logging.INFO)

if not mt5.initialize():
    print("MT5 Init failed")
    exit()

from market.symbol_registry import SymbolRegistry
from strategy.evidence_router import EvidenceRouter
from strategy.indicators import IndicatorCalculator
from data.mt5_client import MT5Client

mt5_client = MT5Client()
mt5_client.connect()
registry = SymbolRegistry("config/symbols.yaml")
evidence_router = EvidenceRouter(base_dir="results")

print("\n--- Testing EvidenceRouter NOW ---")
for symbol_info in registry.get_enabled_symbols():
    symbol = symbol_info["symbol"]
    df = mt5_client.get_historical_data(symbol, "M5", 250)
    if df is None or df.empty:
        continue
    df = IndicatorCalculator.add_indicators(df)
    sig = evidence_router.evaluate(df, symbol)
    if sig:
        print(f"SIGNAL FOUND: {symbol} {sig['direction']} (Sim: {sig['metadata']['similarity_score']:.2f})")
    else:
        print(f"NO SIGNAL: {symbol}")

mt5.shutdown()
