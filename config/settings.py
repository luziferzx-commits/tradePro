import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # MT5 Settings
    MT5_LOGIN = int(os.getenv("MT5_LOGIN", 0))
    MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
    MT5_SERVER = os.getenv("MT5_SERVER", "")
    AI_REVIEW_THRESHOLD: int = int(os.getenv("AI_REVIEW_THRESHOLD", 60))
    EXECUTION_THRESHOLD: int = int(os.getenv("EXECUTION_THRESHOLD", 75))
    MIN_AI_CONFIDENCE: int = int(os.getenv("MIN_AI_CONFIDENCE", 80))
    GLOBAL_SIGNAL_THRESHOLD: float = float(os.getenv("GLOBAL_SIGNAL_THRESHOLD", 0.55))
    SHADOW_MODE: bool = os.getenv("SHADOW_MODE", "False").lower() == "true"
    MT5_PATH = os.getenv("MT5_PATH", "") # Optional path to terminal64.exe
    
    # Trading Parameters
    SYMBOL = os.getenv("SYMBOL", "XAUUSD")
    TIMEFRAME = "M5" # Handled explicitly in mt5_client
    
    # Risk Management
    RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", 0.01))  # 1% risk per trade
    MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", 0.03))  # 3% max daily loss
    MAX_DAILY_LOSS_WARNING_PCT = float(os.getenv("MAX_DAILY_LOSS_WARNING_PCT", 0.02)) # 2% warning
    MAX_DRAWDOWN_PCT = float(os.getenv("MAX_DRAWDOWN_PCT", 0.15))      # 15% max drawdown
    MAX_REAL_RISK_PER_TRADE_PCT = float(os.getenv("MAX_REAL_RISK_PER_TRADE_PCT", 0.02))
    MIN_EVIDENCE_EXPECTANCY_R = float(os.getenv("MIN_EVIDENCE_EXPECTANCY_R", 0.05))
    ENABLE_PAUSED_SYMBOL_RECOVERY_PROBE = os.getenv("ENABLE_PAUSED_SYMBOL_RECOVERY_PROBE", "False").lower() == "true"
    RECOVERY_PROBE_MIN_PF = float(os.getenv("RECOVERY_PROBE_MIN_PF", 1.50))
    RECOVERY_PROBE_MIN_EXPECTANCY_R = float(os.getenv("RECOVERY_PROBE_MIN_EXPECTANCY_R", 0.20))
    RECOVERY_PROBE_MIN_SIMILARITY = float(os.getenv("RECOVERY_PROBE_MIN_SIMILARITY", 0.70))
    MAX_CONSECUTIVE_LOSSES = int(os.getenv("MAX_CONSECUTIVE_LOSSES", 5))
    MAX_SPREAD_POINTS = int(os.getenv("MAX_SPREAD_POINTS", 50))        # e.g., 5.0 pips for Gold
    MAX_SLIPPAGE_POINTS = int(os.getenv("MAX_SLIPPAGE_POINTS", 20))    # Pre-trade signal price drift
    MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", 5))
    TRADE_THROTTLE_MAX_GLOBAL_PER_HOUR = int(os.getenv("TRADE_THROTTLE_MAX_GLOBAL_PER_HOUR", 5))
    TRADE_THROTTLE_MAX_SYMBOL_PER_HOUR = int(os.getenv("TRADE_THROTTLE_MAX_SYMBOL_PER_HOUR", 2))
    MAX_CORRELATED_POSITIONS_PER_GROUP = int(os.getenv("MAX_CORRELATED_POSITIONS_PER_GROUP", 3))
    ENABLE_AUTO_PAUSE_BAD_START = os.getenv("ENABLE_AUTO_PAUSE_BAD_START", "True").lower() == "true"
    AUTO_PAUSE_BAD_START_TRADES = int(os.getenv("AUTO_PAUSE_BAD_START_TRADES", 3))
    AUTO_PAUSE_BAD_START_LOSSES = int(os.getenv("AUTO_PAUSE_BAD_START_LOSSES", 3))
    BAD_START_HARD_PAUSE_REQUIRES_NEGATIVE_PNL = os.getenv("BAD_START_HARD_PAUSE_REQUIRES_NEGATIVE_PNL", "True").lower() == "true"
    AUTO_PAUSE_FLOATING_DD_PCT = float(os.getenv("AUTO_PAUSE_FLOATING_DD_PCT", 0.015))
    ENABLE_DAILY_PROFIT_LOCK = os.getenv("ENABLE_DAILY_PROFIT_LOCK", "True").lower() == "true"
    DAILY_PROFIT_LOCK_PCT = float(os.getenv("DAILY_PROFIT_LOCK_PCT", 0.015))
    DAILY_GUARD_TIMEZONE = os.getenv("DAILY_GUARD_TIMEZONE", "Asia/Bangkok")
    ENABLE_PAUSED_SIGNAL_LOGGING = os.getenv("ENABLE_PAUSED_SIGNAL_LOGGING", "True").lower() == "true"
    LIVE_GUARD_ENTRY_ACTION = os.getenv("LIVE_GUARD_ENTRY_ACTION", "PROBE").upper()
    LIVE_GUARD_PROBE_MULTIPLIER = float(os.getenv("LIVE_GUARD_PROBE_MULTIPLIER", 0.10))
    # Startup safety (opt-in): when True, a mismatch between the local ledger and
    # broker positions at start halts trading and trips the kill switch for
    # manual review. Default False preserves the auto-sync-and-resume design
    # (broker truth is applied to the ledger and trading continues).
    HALT_ON_RECONCILE_MISMATCH = os.getenv("HALT_ON_RECONCILE_MISMATCH", "False").lower() == "true"
    # Position hygiene
    # Close open positions whose symbol has been disabled for live trading.
    AUTO_CLOSE_DISABLED_SYMBOLS = os.getenv("AUTO_CLOSE_DISABLED_SYMBOLS", "False").lower() == "true"
    # Close positions open longer than this many hours (0 = disabled).
    MAX_POSITION_AGE_HOURS = float(os.getenv("MAX_POSITION_AGE_HOURS", 0))
    # Warn (log + Telegram) when open positions reach this fraction of the max.
    POSITION_CAPACITY_ALERT_PCT = float(os.getenv("POSITION_CAPACITY_ALERT_PCT", 0.9))
    # DynamicScaling drawdown ladder (fraction of peak equity):
    #   >= DERISK -> trade at half size (keeps recovering, no deadlock)
    #   >= HALT   -> hard stop (catastrophic circuit breaker)
    DYNAMIC_DD_DERISK_PCT = float(os.getenv("DYNAMIC_DD_DERISK_PCT", 0.05))
    DYNAMIC_DD_HALT_PCT = float(os.getenv("DYNAMIC_DD_HALT_PCT", 0.20))
    # Reject patterns whose backtest PF is at/above this ceiling (overfit guard).
    # 0 = disabled. Live analysis: research PF >= ~1.5 failed, 1.1-1.3 worked.
    PATTERN_PF_CEILING = float(os.getenv("PATTERN_PF_CEILING", 0))
    # Intraday-only: close all positions at/after this UTC hour and stop new
    # entries (avoids holding across the overnight trend/regime flip). -1 = off.
    DAILY_FLAT_CLOSE_HOUR_UTC = int(os.getenv("DAILY_FLAT_CLOSE_HOUR_UTC", -1))
    ENABLE_DEMO_EXPLORATION = os.getenv("ENABLE_DEMO_EXPLORATION", "False").lower() == "true"
    DEMO_EXPLORATION_DAILY_CAP = int(os.getenv("DEMO_EXPLORATION_DAILY_CAP", 20))
    DEMO_EXPLORATION_MAX_PER_SCAN = int(os.getenv("DEMO_EXPLORATION_MAX_PER_SCAN", 2))
    DEMO_EXPLORATION_TARGET_SIGNALS_PER_SCAN = int(os.getenv("DEMO_EXPLORATION_TARGET_SIGNALS_PER_SCAN", 2))
    DEMO_EXPLORATION_MIN_CONFIDENCE = float(os.getenv("DEMO_EXPLORATION_MIN_CONFIDENCE", 0.55))
    DEMO_EXPLORATION_MIN_AVG_R = float(os.getenv("DEMO_EXPLORATION_MIN_AVG_R", 0.05))
    DEMO_EXPLORATION_MIN_WIN_RATE = float(os.getenv("DEMO_EXPLORATION_MIN_WIN_RATE", 0.48))
    DEMO_EXPLORATION_ALLOW_NEUTRAL = os.getenv("DEMO_EXPLORATION_ALLOW_NEUTRAL", "True").lower() == "true"
    ENABLE_ADVANCED_PRICE_ACTION_FILTERS = os.getenv("ENABLE_ADVANCED_PRICE_ACTION_FILTERS", "True").lower() == "true"
    PA_H4_TREND_CONFLICT_ACTION = os.getenv("PA_H4_TREND_CONFLICT_ACTION", "PENALTY").upper()
    PA_H4_SR_ACTION = os.getenv("PA_H4_SR_ACTION", "PENALTY").upper()
    PA_H4_SR_ATR_MULT = float(os.getenv("PA_H4_SR_ATR_MULT", 0.35))
    PA_H1_SR_ATR_MULT = float(os.getenv("PA_H1_SR_ATR_MULT", 0.25))
    PA_TREND_CONFLICT_PENALTY = float(os.getenv("PA_TREND_CONFLICT_PENALTY", 0.85))
    PA_H4_SR_PENALTY = float(os.getenv("PA_H4_SR_PENALTY", 0.90))
    PA_H1_SR_PENALTY = float(os.getenv("PA_H1_SR_PENALTY", 0.92))
    PA_FVG_BOOST = float(os.getenv("PA_FVG_BOOST", 1.08))
    PA_LIQUIDITY_SWEEP_ACTION = os.getenv("PA_LIQUIDITY_SWEEP_ACTION", "REJECT").upper()
    PA_DIVERGENCE_ACTION = os.getenv("PA_DIVERGENCE_ACTION", "REJECT").upper()
    PA_CHOP_THRESHOLD = float(os.getenv("PA_CHOP_THRESHOLD", 61.8))
    PA_CHOP_TREND_PENALTY = float(os.getenv("PA_CHOP_TREND_PENALTY", 0.85))
    PA_VOLUME_DRY_BREAKOUT_PENALTY = float(os.getenv("PA_VOLUME_DRY_BREAKOUT_PENALTY", 0.90))
    PA_USD_CONFLICT_PENALTY = float(os.getenv("PA_USD_CONFLICT_PENALTY", 0.90))
    PA_KILLZONE_OFFHOURS_PENALTY = float(os.getenv("PA_KILLZONE_OFFHOURS_PENALTY", 0.92))
    ENABLE_PA_FILTER_AUTOCALIBRATION = os.getenv("ENABLE_PA_FILTER_AUTOCALIBRATION", "True").lower() == "true"
    PA_CALIBRATION_MIN_SAMPLES = int(os.getenv("PA_CALIBRATION_MIN_SAMPLES", 40))
    PA_CALIBRATION_MIN_CONFIDENCE = float(os.getenv("PA_CALIBRATION_MIN_CONFIDENCE", 0.25))
    PA_CALIBRATION_STRICT_AVG_R = float(os.getenv("PA_CALIBRATION_STRICT_AVG_R", -0.10))
    PA_CALIBRATION_RELAX_AVG_R = float(os.getenv("PA_CALIBRATION_RELAX_AVG_R", 0.20))
    PA_CALIBRATION_IGNORE_AVG_R = float(os.getenv("PA_CALIBRATION_IGNORE_AVG_R", 0.45))
    PA_CALIBRATION_STRICT_WIN_RATE = float(os.getenv("PA_CALIBRATION_STRICT_WIN_RATE", 0.45))
    PA_CALIBRATION_RELAX_WIN_RATE = float(os.getenv("PA_CALIBRATION_RELAX_WIN_RATE", 0.56))
    PA_CALIBRATION_REFRESH_SECONDS = int(os.getenv("PA_CALIBRATION_REFRESH_SECONDS", 300))

    
    # Multi-Market Configuration
    ENABLE_MULTI_ASSET = os.getenv("ENABLE_MULTI_ASSET", "False").lower() == "true"
    ENABLE_PORTFOLIO_RISK = os.getenv("ENABLE_PORTFOLIO_RISK", "False").lower() == "true"
    ENABLE_SIGNAL_JOURNAL = os.getenv("ENABLE_SIGNAL_JOURNAL", "True").lower() == "true"
    ENABLE_DD_GUARD = os.getenv("ENABLE_DD_GUARD", "True").lower() == "true"
    
    MULTI_MARKET = {
        "enabled": ENABLE_MULTI_ASSET,
        "max_symbols_per_scan": 11,
        "scan_interval_seconds": 60,
        "max_open_trades": 5,
        "max_total_open_risk": 0.03,
        "max_daily_loss": 0.05,
        "allow_crypto": True,
        "allow_indices": True,
        "allow_forex": True,
        "allow_metals": True,
        "allow_oil": True,
        "allow_generic_model_fallback": False
    }
    
    # Safety & Execution
    DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
    LIVE_MICRO_MODE = os.getenv("LIVE_MICRO_MODE", "True").lower() == "true"
    ALLOW_LIVE_TRADING = os.getenv("ALLOW_LIVE_TRADING", "False").lower() == "true"
    IS_DEMO_ACCOUNT = os.getenv("IS_DEMO_ACCOUNT", "True").lower() == "true"
    MAGIC_NUMBER = 234000
    MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", 1))
    COOLDOWN_MINUTES = 5
    MIN_EQUITY = float(os.getenv("MIN_EQUITY", "100.0"))
    REQUIRE_STOP_LOSS = os.getenv("REQUIRE_STOP_LOSS", "True").lower() == "true"
    REQUIRE_TAKE_PROFIT = os.getenv("REQUIRE_TAKE_PROFIT", "True").lower() == "true"
    
    # Smart Execution
    USE_SMART_EXECUTION = os.getenv("USE_SMART_EXECUTION", "True").lower() == "true"
    LIMIT_ORDER_EXPIRY_MINUTES = int(os.getenv("LIMIT_ORDER_EXPIRY_MINUTES", 5))
    LIVE_ENGINE_LOCK_PORT = int(os.getenv("LIVE_ENGINE_LOCK_PORT", 49321))
    LEARNING_SOURCE = os.getenv("LEARNING_SOURCE", "LIVE")
    LEARNING_ALLOWED_SOURCES = os.getenv("LEARNING_ALLOWED_SOURCES", "LIVE,SHADOW_VALIDATED")
    DYNAMIC_TARGET_MIN_SAMPLES = int(os.getenv("DYNAMIC_TARGET_MIN_SAMPLES", 100))
    AUTO_DEMOTE_LIVE_PF_THRESHOLD = float(os.getenv("AUTO_DEMOTE_LIVE_PF_THRESHOLD", 1.0))
    AUTO_DEMOTE_MIN_LIVE_TRADES = int(os.getenv("AUTO_DEMOTE_MIN_LIVE_TRADES", 5))
    ENABLE_CRYPTO_FORCE_APPROVE = os.getenv("ENABLE_CRYPTO_FORCE_APPROVE", "False").lower() == "true"
    
    # AI Settings
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    BACKTEST_SPREAD_POINTS = int(os.getenv("BACKTEST_SPREAD_POINTS", 20))
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///trades.db")
    
    # Finnhub
    FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

settings = Settings()
