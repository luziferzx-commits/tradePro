"""scripts/run_runtime_dry_run.py"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Force config overrides BEFORE importing main
os.environ["ENABLE_MULTI_ASSET"] = "True"
os.environ["DRY_RUN"] = "True"

import main
from config.settings import settings

def stop_bot_after_delay():
    time.sleep(5)
    print("\n--- Sending shutdown signal to bot ---")
    main._shutdown_requested = True

if __name__ == "__main__":
    print("=" * 60)
    print(" RUNNING RUNTIME DRY RUN (MULTI-ASSET ENABLED) ")
    print("=" * 60)
    print(f"ENABLE_MULTI_ASSET: {settings.ENABLE_MULTI_ASSET}")
    print(f"DRY_RUN: {settings.DRY_RUN}")
    
    # We will let it run for 5 seconds (enough for 1 loop if mt5 is mocked or fails fast)
    t = threading.Thread(target=stop_bot_after_delay)
    t.start()
    
    main.main()
    print("=" * 60)
    print(" DRY RUN COMPLETE ")
    print("=" * 60)
