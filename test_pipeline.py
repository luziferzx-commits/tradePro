import MetaTrader5 as mt5
import yaml
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestLivePipeline")

if not mt5.initialize():
    print("MT5 Init failed")
    exit()

print("--- Testing Live Pipeline ---")
from market.symbol_registry import SymbolRegistry
from gqos.live.alpha_worker import AlphaWorker
from strategy.evidence_router import EvidenceRouter
from gqos.execution.stages import ExposureStage
from data.mt5_client import MT5Client

mt5_client = MT5Client()
mt5_client.connect()

registry = SymbolRegistry("config/symbols.yaml")
evidence_router = EvidenceRouter()
from strategy.indicators import IndicatorCalculator

for symbol_info in registry.get_enabled_symbols():
    symbol = symbol_info["symbol"]
    print(f"Checking {symbol}...")
    df = mt5_client.get_historical_data(symbol, "M15", 250)
    if df is None or df.empty:
        continue
    df = IndicatorCalculator.add_indicators(df)
    sig = evidence_router.evaluate(df, symbol)
    if sig:
        print(f"Signal found for {symbol}: {sig['direction']}")
    else:
        print(f"No signal for {symbol}")

mt5.shutdown()
