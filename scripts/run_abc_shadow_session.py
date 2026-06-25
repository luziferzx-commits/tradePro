import os
import sys
import time
import logging

# Enforce Shadow Mode Environment Variables
os.environ["STRATEGY_ENGINE"] = "abc_router"
os.environ["DRY_RUN"] = "True"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main import main as live_main

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ShadowSession")

def start_shadow_session():
    logger.info("==================================================")
    logger.info("🛡️ INITIALIZING ABC STRATEGY SHADOW SESSION 🛡️")
    logger.info("STRATEGY_ENGINE: abc_router")
    logger.info("DRY_RUN: True (LIVE ORDERS DISABLED)")
    logger.info("==================================================")
    
    # Run the existing live engine logic which respects DRY_RUN
    try:
        live_main()
    except KeyboardInterrupt:
        logger.info("Shadow session terminated by user.")

if __name__ == '__main__':
    start_shadow_session()
