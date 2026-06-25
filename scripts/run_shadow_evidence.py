import time
import os
import logging
from datetime import datetime

from data.mt5_client import mt5_client
from strategy.indicators import IndicatorCalculator
from strategy.evidence_router import EvidenceRouter
from analysis.knowledge_graph import KnowledgeGraph

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("EvidenceShadowBot")

def main():
    if not mt5_client.connect():
        logger.error("Failed to connect to MT5.")
        return

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    logger.info("Initializing Evidence Router (Loading Pattern Database into Cache)...")
    router = EvidenceRouter(base_dir)
    
    logger.info("Generating Knowledge Coverage Report...")
    kg = KnowledgeGraph(base_dir)
    kg.generate_coverage_report()
    
    symbols = ["XAUUSD", "BTCUSD", "EURUSD", "GBPUSD", "NAS100", "US30", "USDJPY", "AUDUSD", "ETHUSD", "SPX500"]
    logger.info(f"Starting Evidence-Based Shadow Bot on {len(symbols)} markets.")

    try:
        while True:
            for symbol in symbols:
                # Fetch recent 200 candles to compute EMAs and ATR properly
                df = mt5_client.get_historical_data(symbol, "M15", 200)
                if df.empty:
                    continue
                    
                df = IndicatorCalculator.add_indicators(df)
                
                # Query the Universal Database for Evidence
                signal = router.evaluate(df, symbol)
                
                if signal:
                    meta = signal['metadata']
                    logger.info(f"💡 [EVIDENCE MATCH] {symbol} | {signal['direction']} | PF: {meta['historical_pf']} | Sim: {meta['similarity_score']:.2f}")
                    logger.info(f"    -> Historical N={meta['occurrences']} | Pattern: {meta['pattern_id']}")
                    
                    # Ensure symbol is selected
                    import MetaTrader5 as mt5
                    mt5.symbol_select(symbol, True)
                    
                    # Virtual execution log (Shadow mode)
                    logger.info(f"🚀 [SHADOW EXECUTION] {symbol} {signal['direction']} (SL: {signal['sl_mult']} ATR, TP: {signal['tp_mult']} ATR)")
                    
            logger.info("Sleeping for 15 minutes...")
            time.sleep(900)
            
    except KeyboardInterrupt:
        logger.info("Bot shutting down.")
    finally:
        mt5_client.disconnect()

if __name__ == '__main__':
    main()
