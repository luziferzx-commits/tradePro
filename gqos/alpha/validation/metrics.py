import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import scipy.stats as stats

class AlphaValidationMetrics:
    @staticmethod
    def generate_forward_returns(price_df: pd.DataFrame, method: str = "open_to_close", horizon: int = 1) -> pd.Series:
        """
        Generates forward returns ensuring NO lookahead bias.
        Forecast is assumed to be generated at the end of bar t.
        
        methods:
        - "open_to_close": Assumes execution at t+1 open, measures return to t+horizon close.
                           (close[t+horizon] - open[t+1]) / open[t+1]
        - "close_to_close_lag1": Assumes execution at t+1 close, measures return to t+1+horizon close.
                                 (close[t+1+horizon] - close[t+1]) / close[t+1]
        """
        if method == "open_to_close":
            if "open" not in price_df.columns:
                raise ValueError("open_to_close method requires 'open' column in price_df")
            # Shift -1 means bringing t+1 value to t
            exec_price = price_df["open"].shift(-1)
            exit_price = price_df["close"].shift(-horizon)
            fwd_ret = (exit_price - exec_price) / exec_price
        elif method == "close_to_close_lag1":
            exec_price = price_df["close"].shift(-1)
            exit_price = price_df["close"].shift(-(1 + horizon))
            fwd_ret = (exit_price - exec_price) / exec_price
        else:
            raise ValueError(f"Unknown forward return method: {method}")
            
        return fwd_ret

    @staticmethod
    def calculate_ic(forecasts: pd.Series, forward_returns: pd.Series) -> float:
        """Pearson correlation (Information Coefficient)."""
        df = pd.concat([forecasts, forward_returns], axis=1).dropna()
        if len(df) < 2:
            return 0.0
        return float(df.iloc[:, 0].corr(df.iloc[:, 1], method='pearson'))

    @staticmethod
    def calculate_rank_ic(forecasts: pd.Series, forward_returns: pd.Series) -> float:
        """Spearman rank correlation (Rank IC)."""
        df = pd.concat([forecasts, forward_returns], axis=1).dropna()
        if len(df) < 2:
            return 0.0
        return float(df.iloc[:, 0].corr(df.iloc[:, 1], method='spearman'))

    @staticmethod
    def calculate_ic_stability(ic_series: pd.Series) -> float:
        """IC Stability = mean(IC) / std(IC)"""
        if len(ic_series) < 2:
            return 0.0
        std = ic_series.std()
        if std == 0:
            return 0.0
        return float(ic_series.mean() / std)

    @staticmethod
    def forecast_autocorrelation(forecasts: pd.Series, lag: int = 1) -> float:
        """Measures signal persistence."""
        if len(forecasts) < lag + 1:
            return 0.0
        return float(forecasts.autocorr(lag=lag))

    @staticmethod
    def alpha_decay_curve(forecasts: pd.Series, price_df: pd.DataFrame, method: str = "open_to_close", max_horizon: int = 10) -> Dict[int, float]:
        """Calculates IC for multiple horizons to observe alpha decay."""
        decay = {}
        for h in range(1, max_horizon + 1):
            fwd_ret = AlphaValidationMetrics.generate_forward_returns(price_df, method=method, horizon=h)
            ic = AlphaValidationMetrics.calculate_ic(forecasts, fwd_ret)
            decay[h] = ic
        return decay
