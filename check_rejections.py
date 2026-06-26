import MetaTrader5 as mt5
import yaml
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GoldBot.Scanner")

from market.scanner import market_scanner

if not mt5.initialize():
    print("MT5 Init failed")
    exit()

print("--- Running MarketScanner Live Check ---")
valid_signals = market_scanner.scan_markets()

print(f"\nScan complete. Found {len(valid_signals)} valid signals.")
if valid_signals:
    for sig in valid_signals:
        print(f"Valid Signal: {sig['symbol']} {sig['direction']}")
else:
    print("No valid signals found.")

mt5.shutdown()
