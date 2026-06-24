"""scripts/run_shadow_session.py"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- MANDATORY OVERRIDES FOR SHADOW MODE ---
os.environ["ENABLE_MULTI_ASSET"] = "True"
os.environ["DRY_RUN"] = "True"
os.environ["ENABLE_SIGNAL_JOURNAL"] = "True"
os.environ["ENABLE_PORTFOLIO_RISK"] = "True"
os.environ["ENABLE_DD_GUARD"] = "True"

import main
from config.settings import settings

def enforce_dry_run():
    # If something tried to bypass the environment variable, hardcode it
    settings.DRY_RUN = True
    settings.ENABLE_MULTI_ASSET = True

def run_shadow(duration_sec: int = 15):
    print("=" * 60)
    print(" 🚀 STARTING SHADOW MODE SESSION ")
    print("=" * 60)
    
    enforce_dry_run()
    
    if not settings.DRY_RUN:
        print("CRITICAL: DRY_RUN is False! Aborting shadow session.")
        sys.exit(1)
        
    print(f"Shadow Session Duration: {duration_sec}s")
    
    def stop_bot():
        time.sleep(duration_sec)
        print("\n--- Ending shadow session gracefully ---")
        main._shutdown_requested = True
        
    t = threading.Thread(target=stop_bot)
    t.start()
    
    try:
        main.main()
    except Exception as e:
        print(f"Shadow session crashed: {e}")
    
    print("=" * 60)
    print(" 🛑 SHADOW MODE SESSION ENDED ")
    print("=" * 60)

if __name__ == "__main__":
    run_shadow()
