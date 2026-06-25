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
    MAX_CONSECUTIVE_LOSSES = int(os.getenv("MAX_CONSECUTIVE_LOSSES", 5))
    MAX_SPREAD_POINTS = int(os.getenv("MAX_SPREAD_POINTS", 50))        # e.g., 5.0 pips for Gold
    MAX_SLIPPAGE_POINTS = int(os.getenv("MAX_SLIPPAGE_POINTS", 20))    # Pre-trade signal price drift
    MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", 5))

    
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
    LIVE_MICRO_MODE = os.getenv("LIVE_MICRO_MODE", "False").lower() == "true"
    ALLOW_LIVE_TRADING = os.getenv("ALLOW_LIVE_TRADING", "False").lower() == "true"
    IS_DEMO_ACCOUNT = os.getenv("IS_DEMO_ACCOUNT", "True").lower() == "true"
    MAGIC_NUMBER = 234000
    MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", 1))
    COOLDOWN_MINUTES = 5
    MIN_EQUITY = float(os.getenv("MIN_EQUITY", "100.0"))
    REQUIRE_STOP_LOSS = os.getenv("REQUIRE_STOP_LOSS", "True").lower() == "true"
    REQUIRE_TAKE_PROFIT = os.getenv("REQUIRE_TAKE_PROFIT", "True").lower() == "true"
    
    # AI Settings
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    BACKTEST_SPREAD_POINTS = int(os.getenv("BACKTEST_SPREAD_POINTS", 20))
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///trades.db")
    
    # Finnhub
    FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

settings = Settings()
