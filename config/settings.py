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
    SHADOW_MODE: bool = os.getenv("SHADOW_MODE", "False").lower() == "true"
    MT5_PATH = os.getenv("MT5_PATH", "") # Optional path to terminal64.exe
    
    # Trading Parameters
    SYMBOL = os.getenv("SYMBOL", "XAUUSD")
    TIMEFRAME = "M5" # Handled explicitly in mt5_client
    
    # Risk Management
    RISK_PER_TRADE_PCT = 0.01  # 1% risk per trade
    MAX_DAILY_LOSS_PCT = 0.05  # 5% max daily loss
    MAX_DRAWDOWN_PCT = 0.15    # 15% max drawdown
    MAX_CONSECUTIVE_LOSSES = 5
    MAX_SPREAD_POINTS = 50     # e.g., 5.0 pips for Gold
    
    # Multi-Market Configuration
    MULTI_MARKET = {
        "enabled": True,
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
    IS_DEMO_ACCOUNT = os.getenv("IS_DEMO_ACCOUNT", "True").lower() == "true"
    MAGIC_NUMBER = 234000
    MAX_OPEN_POSITIONS = 1
    COOLDOWN_MINUTES = 5
    MIN_EQUITY = float(os.getenv("MIN_EQUITY", "100.0"))
    
    # AI Settings
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = "gemini-2.5-flash"
    MIN_AI_CONFIDENCE = 85
    AI_REVIEW_THRESHOLD = 75
    EXECUTION_THRESHOLD = 85
    BACKTEST_SPREAD_POINTS = 20
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///trades.db")
    
    # Finnhub
    FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")

settings = Settings()
