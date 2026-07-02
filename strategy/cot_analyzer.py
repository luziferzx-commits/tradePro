import os
import time
import logging
import pandas as pd
from datetime import datetime
import cot_reports as cot

logger = logging.getLogger(__name__)

class COTAnalyzer:
    _cached_df = None
    _last_update = 0
    _UPDATE_INTERVAL = 86400  # 1 day

    SYMBOL_MAP = {
        "XAUUSD": "GOLD - COMMODITY EXCHANGE INC.",
        "XAGUSD": "SILVER - COMMODITY EXCHANGE INC.",
        "EURUSD": "EURO FX - CHICAGO MERCANTILE EXCHANGE",
        "GBPUSD": "BRITISH POUND - CHICAGO MERCANTILE EXCHANGE",
        "USDJPY": "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE",
        "USDCAD": "CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE",
        "AUDUSD": "AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE",
        "NZDUSD": "NEW ZEALAND DOLLAR - CHICAGO MERCANTILE EXCHANGE",
        "BTCUSD": "BITCOIN - CHICAGO MERCANTILE EXCHANGE",
        "USOIL": "CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE",
    }

    @classmethod
    def _fetch_data(cls):
        now = time.time()
        if cls._cached_df is not None and (now - cls._last_update) < cls._UPDATE_INTERVAL:
            return cls._cached_df

        try:
            year = datetime.now().year
            logger.info(f"Downloading COT Report for {year}...")
            # cot_reports automatically saves to annual.txt
            df = cot.cot_year(year=year, cot_report_type='legacy_fut')
            
            # Filter only latest date
            df['As of Date in Form YYYY-MM-DD'] = pd.to_datetime(df['As of Date in Form YYYY-MM-DD'])
            latest_date = df['As of Date in Form YYYY-MM-DD'].max()
            df_latest = df[df['As of Date in Form YYYY-MM-DD'] == latest_date].copy()
            
            cls._cached_df = df_latest
            cls._last_update = now
            logger.info(f"[COTAnalyzer] Data updated for {latest_date.date()}")
            return cls._cached_df
            
        except Exception as e:
            logger.error(f"[COTAnalyzer] Failed to fetch data: {e}")
            return cls._cached_df

    @classmethod
    def get_net_position(cls, symbol: str) -> dict:
        """
        Returns net non-commercial positions (Hedge Funds) for a symbol.
        Direction is BULLISH if Net > 0, BEARISH if Net < 0.
        Note: For USDJPY, USDCAD (USD is base), the futures contract is on JPY, CAD.
        So if JPY futures are BULLISH, USDJPY is BEARISH.
        """
        # Strip 'm' suffix
        base_symbol = symbol[:-1] if symbol.endswith('m') else symbol
        
        market_name = cls.SYMBOL_MAP.get(base_symbol)
        if not market_name:
            return None

        df = cls._fetch_data()
        if df is None or df.empty:
            return None

        row = df[df['Market and Exchange Names'] == market_name]
        if row.empty:
            return None
            
        row = row.iloc[0]
        
        try:
            longs = int(row['Noncommercial Positions-Long (All)'])
            shorts = int(row['Noncommercial Positions-Short (All)'])
            net = longs - shorts
            
            # Invert signal for pairs where the future is the quote currency
            # e.g., JPY futures go up -> JPY strengthens -> USDJPY goes down.
            if base_symbol in ["USDJPY", "USDCAD"]:
                net = -net
                
            direction = "BULLISH" if net > 0 else "BEARISH"
            
            return {
                "symbol": base_symbol,
                "net_position": net,
                "direction": direction,
                "longs": longs,
                "shorts": shorts
            }
        except Exception as e:
            logger.warning(f"[COTAnalyzer] Error parsing row for {base_symbol}: {e}")
            return None
