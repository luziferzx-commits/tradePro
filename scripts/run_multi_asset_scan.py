"""scripts/run_multi_asset_scan.py"""
import os
import sys
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from market.symbol_registry import SymbolRegistry
from market.market_metadata import MarketMetadata
from scanner.multi_asset_scanner import MultiAssetScanner
from journal.trade_journal import TradeJournal

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("ScanRunner")

def run_scan():
    print("=" * 70)
    print(" MULTI-ASSET SCANNER ")
    print("=" * 70)
    
    registry = SymbolRegistry("config/symbols.yaml")
    metadata = MarketMetadata(registry)
    
    # Intentionally passing None for mt5_client to use mock/fallback mode
    scanner = MultiAssetScanner(registry, metadata, mt5_client=None)
    journal = TradeJournal()
    
    approved, rejected = scanner.scan_all()
    
    print(f"\n✅ APPROVED OPPORTUNITIES ({len(approved)}):")
    for sig in approved:
        journal.log_signal(sig)
        print(f"[{sig['symbol']}] {sig['side']} | Score: {sig['final_score']} | Prob: {sig['model_probability']:.2f} | R: {sig['expected_r']:.1f} | Spread: {sig['spread_points']}")
        
    print(f"\n❌ REJECTED SIGNALS ({len(rejected)}):")
    for sig in rejected:
        journal.log_signal(sig)
        print(f"[{sig['symbol']}] {sig.get('side', 'UNKNOWN')} | Reason: {sig['reason']}")
        
    print("\n" + "=" * 70)
    logger.info("Scan complete. Signals logged to results/signals_journal.csv")

if __name__ == "__main__":
    run_scan()
