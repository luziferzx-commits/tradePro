"""scripts/activate_shadow_mode.py — Pre-flight checklist for transitioning to SHADOW_MODE."""
import os
import sys
import logging
import pandas as pd
import requests

# Add root directory to path to allow imports when run standalone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.settings import settings
from database.repository import repository
from database.models import MarketState
from risk.sl_tp_calculator import SLTPCalculator
import MetaTrader5 as mt5

logger = logging.getLogger("PreFlight")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def run_checklist():
    all_passed = True
    print("=" * 60)
    print(" SHADOW_MODE PRE-FLIGHT CHECKLIST ")
    print("=" * 60)

    # 1. MT5 Connection
    try:
        init_ok = mt5.initialize()
        term = mt5.terminal_info()
        if init_ok and term is not None:
            print("[PASS] 1. MT5 Connection    — Terminal connected.")
        else:
            print("[FAIL] 1. MT5 Connection    — Failed to initialize or get terminal_info().")
            all_passed = False
    except Exception as e:
        print(f"[FAIL] 1. MT5 Connection    — Exception: {e}")
        all_passed = False

    # 2. Account Info
    try:
        acc = mt5.account_info()
        if acc is not None and acc.balance > 0:
            print(f"[PASS] 2. Account Info      — Balance valid: {acc.balance}")
        else:
            print("[FAIL] 2. Account Info      — Balance zero or None.")
            all_passed = False
    except Exception as e:
        print(f"[FAIL] 2. Account Info      — Exception: {e}")
        all_passed = False

    # 3. Symbol Valid
    try:
        symbol = settings.SYMBOL
        sym_info = mt5.symbol_info(symbol)
        if sym_info is not None and sym_info.trade_mode != mt5.SYMBOL_TRADE_MODE_DISABLED:
            print(f"[PASS] 3. Symbol Valid      — {symbol} is valid and tradeable.")
        else:
            print(f"[FAIL] 3. Symbol Valid      — {symbol} disabled or None.")
            all_passed = False
    except Exception as e:
        print(f"[FAIL] 3. Symbol Valid      — Exception: {e}")
        all_passed = False

    # 4. DB Connection
    try:
        with repository.get_session() as session:
            session.query(MarketState).first()  # Just check if we can query
            print("[PASS] 4. DB Connection     — Successfully queried MarketState table.")
    except Exception as e:
        print(f"[FAIL] 4. DB Connection     — Exception: {e}")
        all_passed = False

    # 5. ML Model File
    try:
        # Check standard path or settings
        model_path = getattr(settings, "MODEL_PATH", "models/xgboost_model.pkl")
        if os.path.exists(model_path):
            print(f"[PASS] 5. ML Model File     — Found at {model_path}")
        else:
            print(f"[FAIL] 5. ML Model File     — Missing at {model_path}. Train model first.")
            all_passed = False
    except Exception as e:
        print(f"[FAIL] 5. ML Model File     — Exception: {e}")
        all_passed = False

    # 6. Feature Store
    try:
        # Assuming feature store might be in features/ or ml/
        try:
            import features.feature_store
            print("[PASS] 6. Feature Store     — Imported features.feature_store OK.")
        except ImportError:
            import ml.feature_store
            print("[PASS] 6. Feature Store     — Imported ml.feature_store OK.")
    except Exception as e:
        print(f"[FAIL] 6. Feature Store     — Could not import feature_store. Exception: {e}")
        all_passed = False

    # 7. Risk Settings
    try:
        max_loss = getattr(settings, "MAX_DAILY_LOSS_PCT", 0.0)
        if 0.01 <= max_loss <= 0.10:
            print(f"[PASS] 7. Risk Settings     — MAX_DAILY_LOSS_PCT is sane ({max_loss}).")
        else:
            print(f"[FAIL] 7. Risk Settings     — MAX_DAILY_LOSS_PCT ({max_loss}) outside sane range [0.01-0.10].")
            all_passed = False
    except Exception as e:
        print(f"[FAIL] 7. Risk Settings     — Exception: {e}")
        all_passed = False

    # 8. SL Calc Sanity
    try:
        df = pd.DataFrame({"atr": [20.0]})
        result = SLTPCalculator.calculate(df, "BUY")
        sl = result["sl_points"]
        if 150 <= sl <= 2000:
            print(f"[PASS] 8. SL Calc Sanity    — SL={sl}pts is within valid range [150-2000].")
        else:
            print(f"[FAIL] 8. SL Calc Sanity    — SL={sl}pts outside valid bounds.")
            all_passed = False
    except Exception as e:
        print(f"[FAIL] 8. SL Calc Sanity    — Exception: {e}")
        all_passed = False

    # 9. Log File Writable
    try:
        log_path = "goldbot.log"
        with open(log_path, "a") as f:
            f.write("")
        print(f"[PASS] 9. Log File Writable — {log_path} is accessible.")
    except Exception as e:
        print(f"[FAIL] 9. Log File Writable — Cannot write to {log_path}. Exception: {e}")
        all_passed = False

    # 10. Telegram Reachable (Optional)
    try:
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        if not token:
            print("[-]   10. Telegram Reachable  — Skipped (no token set).")
        else:
            url = f"https://api.telegram.org/bot{token}/getMe"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                print("[PASS] 10. Telegram Reachable — API returned 200 OK.")
            else:
                print(f"[-]   10. Telegram Reachable  — Failed (Status {resp.status_code}), but non-critical.")
    except Exception as e:
        print(f"[-]   10. Telegram Reachable  — Exception: {e} (non-critical).")

    print("=" * 60)
    
    if all_passed:
        print("✅ PRE-FLIGHT PASSED — Safe to switch to SHADOW_MODE")
        print("\nINSTRUCTION:")
        print("Set SHADOW_MODE=True and DRY_RUN=False in your .env file, then restart.")
    else:
        print("❌ PRE-FLIGHT FAILED — Fix issues above before switching")

    mt5.shutdown()


if __name__ == "__main__":
    run_checklist()
