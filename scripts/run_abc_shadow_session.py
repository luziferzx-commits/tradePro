import os
import sys
import time
import logging

# Hard Safety Assertions (Pre-Init)
os.environ["STRATEGY_ENGINE"] = "abc_router"
os.environ["DRY_RUN"] = "True"

assert os.getenv("DRY_RUN") == "True", "FATAL: DRY_RUN must be True for Shadow Session!"
assert os.getenv("STRATEGY_ENGINE") == "abc_router", "FATAL: STRATEGY_ENGINE must be abc_router!"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main import main as live_main
from execution.executor import Executor

# Monkey-patch the live executor to raise RuntimeError if it's called
def _safe_execute(*args, **kwargs):
    raise RuntimeError("FATAL: Live order execution attempted during Shadow Session! Emergency Stop!")

Executor.execute_order = _safe_execute
Executor.close_position = _safe_execute
Executor.modify_position = _safe_execute

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ShadowSession")

import threading

def shadow_heartbeat():
    while True:
        logger.info(f"SHADOW_HEARTBEAT | "
                    f"timestamp={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} | "
                    f"symbol=XAUUSD | "
                    f"strategy_engine={os.getenv('STRATEGY_ENGINE')} | "
                    f"dry_run={os.getenv('DRY_RUN')} | "
                    f"router_status=ACTIVE")
        time.sleep(300) # Every 5 minutes

def start_shadow_session():
    logger.info("==================================================")
    logger.info("🛡️ INITIALIZING ABC STRATEGY SHADOW SESSION 🛡️")
    logger.info("STRATEGY_ENGINE: abc_router")
    logger.info("DRY_RUN: True (LIVE ORDERS DISABLED)")
    logger.info("BROKER ADAPTER: MOCKED (RuntimeError on execution)")
    logger.info("==================================================")
    
    hb_thread = threading.Thread(target=shadow_heartbeat, daemon=True)
    hb_thread.start()
    
    try:
        live_main()
    except KeyboardInterrupt:
        logger.info("Shadow session terminated by user.")

if __name__ == '__main__':
    start_shadow_session()
