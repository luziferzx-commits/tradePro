import os
import sys
import time
import logging
import threading
import pandas as pd
import json
from datetime import datetime

# Hard Safety Assertions (Pre-Init)
os.environ["STRATEGY_ENGINE"] = "abc_router"
os.environ["DRY_RUN"] = "True"

assert os.getenv("DRY_RUN") == "True", "FATAL: DRY_RUN must be True for Shadow Session!"
assert os.getenv("STRATEGY_ENGINE") == "abc_router", "FATAL: STRATEGY_ENGINE must be abc_router!"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main import main as live_main
from execution.executor import Executor
from market.scanner import market_scanner
from strategy.evidence_router import EvidenceRouter
from data.mt5_client import mt5_client

# Monkey-patch the live executor to raise RuntimeError if it's called
def _safe_execute(*args, **kwargs):
    raise RuntimeError("FATAL: Live order execution attempted during Shadow Session! Emergency Stop!")

Executor.execute_order = _safe_execute
Executor.close_position = _safe_execute
Executor.modify_position = _safe_execute

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ShadowSession")

# Parallel Shadow Setup
evidence_shadow_enabled = os.getenv("EVIDENCE_ROUTER_SHADOW", "false").lower() == "true"
evidence_router = None
if evidence_shadow_enabled:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    evidence_router = EvidenceRouter(base_dir, mode="SHADOW")

original_scan = market_scanner.scan_markets

def parallel_scan_markets():
    # 1. Run standard ABC scan
    valid_signals = original_scan()
    
    # 2. Run EvidenceRouter scan in parallel
    if evidence_shadow_enabled and evidence_router:
        from strategy.indicators import IndicatorCalculator
        for symbol in ["XAUUSD", "BTCUSD", "EURUSD", "GBPUSD", "NAS100", "US30", "USDJPY", "AUDUSD", "ETHUSD", "SPX500"]:
            df = mt5_client.get_historical_data(symbol, "M15", 250)
            if not df.empty:
                df = IndicatorCalculator.add_indicators(df)
                evidence_signal = evidence_router.evaluate(df, symbol)
                if evidence_signal:
                    logger.info(f"💡 [EVIDENCE SHADOW] {symbol} {evidence_signal['direction']} | PF: {evidence_signal['metadata']['historical_pf']} | Sim: {evidence_signal['metadata']['similarity_score']}")
                    
                    try:
                        from notifications.telegram_notifier import send_telegram
                        promo = evidence_signal['metadata'].get('promotion_status', 'UNKNOWN')
                        msg = (
                            f"💡 <b>[SHADOW MODE] TRADE FOUND!</b>\n"
                            f"─────────────────\n"
                            f"Symbol  : <b>{symbol}</b>\n"
                            f"Action  : <b>{evidence_signal['direction']}</b>\n"
                            f"Sim     : {evidence_signal['metadata']['similarity_score'] * 100:.1f}%\n"
                            f"PF      : {evidence_signal['metadata']['historical_pf']:.2f}\n"
                            f"Promo   : {promo}\n"
                            f"─────────────────\n"
                            f"<i>*This is a virtual paper-trade by EvidenceRouter</i>"
                        )
                        send_telegram(msg)
                    except Exception as e:
                        logger.error(f"Failed to send shadow telegram: {e}")
                    
                    # Log structured data for later outcome evaluation
                    log_dir = os.path.join(base_dir, "data", "shadow_store")
                    os.makedirs(log_dir, exist_ok=True)
                    log_file = os.path.join(log_dir, "evidence_signals.jsonl")
                    
                    record = {
                        "timestamp": datetime.now().isoformat(),
                        "symbol": symbol,
                        "direction": evidence_signal['direction'],
                        "entry_price": float(df.iloc[-1]['close']),
                        "sl_mult": evidence_signal['sl_mult'],
                        "tp_mult": evidence_signal['tp_mult'],
                        "horizon": evidence_signal['horizon'],
                        "historical_pf": evidence_signal['metadata']['historical_pf'],
                        "similarity_score": evidence_signal['metadata']['similarity_score'],
                        "occurrences": evidence_signal['metadata']['occurrences'],
                        "pattern_id": evidence_signal['metadata']['pattern_id']
                    }
                    
                    with open(log_file, "a") as f:
                        f.write(json.dumps(record) + "\n")
                        
                    # Also append to the markdown report for quick viewing
                    report_path = os.path.join(base_dir, "reports", "EVIDENCE_ROUTER_SHADOW_REPORT.md")
                    os.makedirs(os.path.dirname(report_path), exist_ok=True)
                    with open(report_path, "a") as f:
                        f.write(f"| {time.strftime('%Y-%m-%d %H:%M:%S')} | {symbol} | {evidence_signal['direction']} | {evidence_signal['metadata']['historical_pf']} | {evidence_signal['metadata']['similarity_score']} | {evidence_signal['metadata']['occurrences']} |\n")

    return valid_signals

market_scanner.scan_markets = parallel_scan_markets

def shadow_heartbeat():
    while True:
        logger.info(f"SHADOW_HEARTBEAT | "
                    f"timestamp={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} | "
                    f"router_status=ACTIVE | evidence_shadow={evidence_shadow_enabled}")
        time.sleep(300)

def start_shadow_session():
    logger.info("==================================================")
    logger.info("🛡️ INITIALIZING ABC STRATEGY SHADOW SESSION 🛡️")
    logger.info("EVIDENCE_ROUTER_SHADOW: " + str(evidence_shadow_enabled))
    logger.info("==================================================")
    
    if evidence_shadow_enabled:
        report_path = os.path.join(base_dir, "reports", "EVIDENCE_ROUTER_SHADOW_REPORT.md")
        if not os.path.exists(report_path):
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            with open(report_path, "w") as f:
                f.write("# Evidence Router Shadow Report\n\n| Time | Symbol | Direction | Hist PF | Sim Score | N |\n|---|---|---|---|---|---|\n")
    
    hb_thread = threading.Thread(target=shadow_heartbeat, daemon=True)
    hb_thread.start()
    
    try:
        live_main()
    except KeyboardInterrupt:
        logger.info("Shadow session terminated by user.")

if __name__ == '__main__':
    start_shadow_session()
