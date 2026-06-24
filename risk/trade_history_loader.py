"""risk/trade_history_loader.py — Loads and normalizes trade history for survivability testing."""
import os
import glob
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

class TradeHistoryLoader:
    SEARCH_PATHS = [
        "results/trades.csv",
        "results/trade_history.csv",
        "results/backtest_trades.csv",
        "results/context_preds.csv",
        "reports/*trades*.csv",
        "reports/*backtest*.csv"
    ]

    PNL_COLUMNS = [
        "pnl", "profit", "return", "r_multiple", "R", "result_R", "net_pnl", "trade_return"
    ]

    @staticmethod
    def load_history() -> tuple[pd.DataFrame, bool]:
        """
        Attempts to load real trade history.
        Returns:
            df: DataFrame containing at least 'r_multiple' column.
            is_synthetic: Boolean indicating if fallback synthetic data was used.
        """
        for path_pattern in TradeHistoryLoader.SEARCH_PATHS:
            for file_path in glob.glob(path_pattern):
                try:
                    df = pd.read_csv(file_path)
                    
                    # Look for explicit PNL/R columns
                    found_col = None
                    for col in df.columns:
                        if col.lower() in [c.lower() for c in TradeHistoryLoader.PNL_COLUMNS]:
                            found_col = col
                            break
                            
                    if found_col:
                        logger.info(f"Loaded real trade history from {file_path} using column '{found_col}'")
                        return TradeHistoryLoader._normalize(df, file_path, r_col=found_col), False
                        
                    # If not found, look for win/loss indicator like 'label' or 'win'
                    if 'label' in df.columns:
                        logger.info(f"Loaded real trade history from {file_path} using 'label' column (conservative R mapping)")
                        return TradeHistoryLoader._normalize(df, file_path, label_col='label'), False
                    
                    if 'win' in df.columns:
                        logger.info(f"Loaded real trade history from {file_path} using 'win' column (conservative R mapping)")
                        return TradeHistoryLoader._normalize(df, file_path, label_col='win'), False

                except Exception as e:
                    logger.warning(f"Failed to read {file_path}: {e}")
                    continue
                    
        # If no real history found, fallback
        logger.warning("No real trade history found. Generating SYNTHETIC fallback.")
        return TradeHistoryLoader._generate_synthetic_fallback(), True

    @staticmethod
    def _normalize(df: pd.DataFrame, source: str, r_col: str = None, label_col: str = None) -> pd.DataFrame:
        norm_df = pd.DataFrame()
        
        # Extract R multiple
        if r_col:
            # Drop NaN and Inf
            valid_mask = np.isfinite(df[r_col].values)
            df = df[valid_mask].copy()
            norm_df['r_multiple'] = df[r_col].astype(float)
        elif label_col:
            valid_mask = df[label_col].notna()
            df = df[valid_mask].copy()
            # conservative: win = +1R, loss = -1R
            norm_df['r_multiple'] = np.where(df[label_col] == 1, 1.0, -1.0)
            
        if len(norm_df) == 0:
            return TradeHistoryLoader._generate_synthetic_fallback()
            
        norm_df['source_file'] = source
        norm_df['timestamp'] = df.get('timestamp', df.get('time', pd.NaT))
        norm_df['symbol'] = df.get('symbol', 'UNKNOWN')
        norm_df['side'] = df.get('side', df.get('direction', 'UNKNOWN'))
        
        # Outlier detection
        outliers = norm_df[(norm_df['r_multiple'] > 20.0) | (norm_df['r_multiple'] < -20.0)]
        if not outliers.empty:
            logger.warning(f"Detected {len(outliers)} outlier trades with R > 20 or < -20. Clipping values.")
            norm_df['r_multiple'] = norm_df['r_multiple'].clip(-20.0, 20.0)
            
        # Minimum trades warning
        if len(norm_df) < 100:
            logger.warning(f"Trade history contains only {len(norm_df)} trades. Survivability metrics may be statistically unreliable.")
            
        return norm_df

    @staticmethod
    def _generate_synthetic_fallback() -> pd.DataFrame:
        n_trades = 500
        # Win rate 30%, 2R reward, -1R loss
        r_multiples = [2.0 if np.random.rand() < 0.30 else -1.0 for _ in range(n_trades)]
        df = pd.DataFrame({
            'r_multiple': r_multiples,
            'source_file': 'SYNTHETIC_FALLBACK',
            'timestamp': pd.NaT,
            'symbol': 'SYNTHETIC',
            'side': 'UNKNOWN'
        })
        return df
