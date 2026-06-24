"""scripts/run_multi_shadow.py"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# --- MANDATORY OVERRIDES FOR SHADOW MODE ---
os.environ["ENABLE_MULTI_ASSET"] = "True"
os.environ["DRY_RUN"] = "True"
os.environ["LIVE_MICRO_MODE"] = "False"
os.environ["ENABLE_SIGNAL_JOURNAL"] = "True"
os.environ["ENABLE_PORTFOLIO_RISK"] = "True"
os.environ["ENABLE_DD_GUARD"] = "True"

import main
from config.settings import settings

def run_shadow_mode():
    print("=" * 60)
    print(" 👻 STARTING SHADOW MODE (DRY RUN) ")
    print("=" * 60)
    
    # Force apply to settings
    settings.ENABLE_MULTI_ASSET = True
    settings.DRY_RUN = True
    settings.LIVE_MICRO_MODE = False
    
    print("INFO: This mode will NOT execute real trades.")
    print("All trades will be logged to the shadow_trades database table.")
    print("Press Ctrl+C to stop.")
    print("=" * 60)
    
    main.main()

if __name__ == "__main__":
    run_shadow_mode()
