import pandas as pd
import numpy as np
from typing import Dict

class BenchmarkEngine:
    @staticmethod
    def calculate_baselines(market_returns: pd.Series, risk_free_rate: float = 0.0) -> Dict[str, pd.Series]:
        """
        Calculates standard baselines from a market return series.
        """
        n = len(market_returns)
        
        # 1. Buy & Hold
        buy_hold = market_returns.copy()
        
        # 2. Random Signal (-1, 0, 1)
        np.random.seed(42) # For reproducibility in campaign
        rand_signal = np.random.choice([-1, 0, 1], size=n)
        random_signal_ret = market_returns * rand_signal
        
        # 3. Random Long Only (0, 1)
        rand_long = np.random.choice([0, 1], size=n)
        random_long_ret = market_returns * rand_long
        
        # 4. Simple Mean Reversion (Simulated inverse of past return)
        mr_signal = -np.sign(market_returns.shift(1).fillna(0))
        mr_ret = market_returns * mr_signal
        
        return {
            "buy_and_hold": buy_hold,
            "random_signal": random_signal_ret,
            "random_long_only": random_long_ret,
            "simple_mean_reversion": mr_ret
        }

    @staticmethod
    def evaluate_alpha(alpha_returns: pd.Series, benchmark_returns: pd.Series) -> Dict[str, float]:
        """
        Evaluates Alpha performance relative to a specific benchmark.
        """
        excess_return = alpha_returns - benchmark_returns
        tracking_error = excess_return.std() * np.sqrt(252) # Annualized
        
        mean_excess_ann = excess_return.mean() * 252
        
        information_ratio = mean_excess_ann / tracking_error if tracking_error > 0 else 0.0
        
        return {
            "excess_return_ann": mean_excess_ann,
            "tracking_error_ann": tracking_error,
            "information_ratio": information_ratio
        }
