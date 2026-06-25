"""scripts/activate_live_micro.py"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- MANDATORY OVERRIDES FOR LIVE MICRO MODE ---
os.environ["ENABLE_MULTI_ASSET"] = "True"
os.environ["DRY_RUN"] = "False"
os.environ["LIVE_MICRO_MODE"] = "True"
os.environ["ENABLE_SIGNAL_JOURNAL"] = "True"
os.environ["ENABLE_PORTFOLIO_RISK"] = "True"
os.environ["ENABLE_DD_GUARD"] = "True"

import main
from config.settings import settings

def run_live_micro():
    print("=" * 60)
    print(" 🚀 STARTING LIVE MICRO MODE (0.01 LOT MAX) ")
    print("=" * 60)
    
    # Force apply to settings
    settings.ENABLE_MULTI_ASSET = True
    settings.DRY_RUN = False
    settings.LIVE_MICRO_MODE = True
    
    print("WARNING: THIS WILL EXECUTE REAL TRADES IN MT5!")
    print("All volumes are strictly capped at 0.01 lots.")
    print("Press Ctrl+C to stop.")
    print("=" * 60)
    
    try:
        main.main()
    except KeyboardInterrupt:
        print("\n--- Ending Live Micro session gracefully ---")
        main._shutdown_requested = True
    except Exception as e:
        print(f"Live Micro session crashed: {e}")
    
    print("=" * 60)
    print(" 🛑 LIVE MICRO MODE ENDED ")
    print("=" * 60)

if __name__ == "__main__":
    run_live_micro()
