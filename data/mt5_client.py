import MetaTrader5 as mt5
import pandas as pd
import logging
from datetime import datetime
from config.settings import settings
import yaml
import os

logger = logging.getLogger(__name__)

class MT5Client:
    def __init__(self):
        self.connected = False
        self.aliases = self._load_aliases()

    def _load_aliases(self):
        try:
            with open("config/symbols.yaml", "r") as f:
                cfg = yaml.safe_load(f)
                return cfg.get("symbol_aliases", {})
        except Exception as e:
            logger.error(f"Failed to load symbol aliases: {e}")
            return {}

    def resolve_symbol(self, symbol: str) -> str:
        return self.aliases.get(symbol, symbol)

    def connect(self) -> bool:
        # Pass credentials directly to initialize() to prevent Error -6 (Authorization Failed)
        init_kwargs = {
            "login": settings.MT5_LOGIN, 
            "password": settings.MT5_PASSWORD, 
            "server": settings.MT5_SERVER
        }
        if hasattr(settings, 'MT5_PATH') and settings.MT5_PATH:
            init_kwargs["path"] = settings.MT5_PATH
            
        if not mt5.initialize(**init_kwargs):
            logger.error(f"MT5 initialize() failed, error code = {mt5.last_error()}")
            return False
            
        # login() is usually not necessary if initialize() with credentials succeeds, 
        # but we do it anyway to be strictly compliant
        authorized = mt5.login(
            settings.MT5_LOGIN, 
            password=settings.MT5_PASSWORD, 
            server=settings.MT5_SERVER
        )
        if not authorized:
            logger.error(f"MT5 login failed, error code = {mt5.last_error()}")
            return False
            
        self.connected = True
        logger.info(f"Connected to MT5 Server: {settings.MT5_SERVER}")
        return True

    def disconnect(self):
        if self.connected:
            mt5.shutdown()
            self.connected = False
            logger.info("Disconnected from MT5")

    def is_new_candle(self) -> bool:
        """Fallback is_new_candle to satisfy main.py loop condition. Sleep handles timing."""
        return True

    def get_historical_data(self, symbol: str, timeframe: str, num_candles: int) -> pd.DataFrame:
        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "H1": mt5.TIMEFRAME_H1,
            "D1": mt5.TIMEFRAME_D1
        }
        mt5_tf = tf_map.get(timeframe, mt5.TIMEFRAME_M5)
        resolved_symbol = self.resolve_symbol(symbol)
        
        # Ensure symbol is visible in Market Watch before fetching data
        if not mt5.symbol_select(resolved_symbol, True):
            logger.error(f"Failed to select symbol {resolved_symbol} (original: {symbol}) in Market Watch.")
            return pd.DataFrame()
            
        rates = mt5.copy_rates_from_pos(resolved_symbol, mt5_tf, 0, num_candles + 1)
        if rates is None:
            logger.error(f"Failed to get data for {symbol}. Error: {mt5.last_error()}")
            return pd.DataFrame()
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Ensure we only process fully closed candles
        # The latest candle at index -1 is currently forming, so we drop it
        return df.iloc[:-1].copy()

    def get_symbol_info(self, symbol: str):
        resolved_symbol = self.resolve_symbol(symbol)
        return mt5.symbol_info(resolved_symbol)

    def get_h4_data(self, symbol: str, count: int = 50) -> pd.DataFrame | None:
        resolved_symbol = self.resolve_symbol(symbol)
        if not mt5.symbol_select(resolved_symbol, True):
            return None
        rates = mt5.copy_rates_from_pos(resolved_symbol, mt5.TIMEFRAME_H4, 0, count)
        if rates is None:
            return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

mt5_client = MT5Client()
