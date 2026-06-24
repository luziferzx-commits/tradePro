import numpy as np
import pandas as pd
from typing import List, Dict
import scipy.stats as stats

from gqos.research.factory.generators import TemplateAlpha

class DeflatedSharpeRatio:
    """
    Calculates the Deflated Sharpe Ratio (DSR) to account for selection bias.
    DSR computes the probability that the Sharpe Ratio is greater than zero
    given the number of trials (permutations) and the variance of the trials.
    """
    @staticmethod
    def calculate(sharpe: float, trial_sharpes: List[float], skew: float, kurtosis: float, sample_size: int) -> float:
        if len(trial_sharpes) <= 1:
            return 1.0 # Cannot deflate a single trial
            
        n_trials = len(trial_sharpes)
        var_trials = np.var(trial_sharpes)
        
        # Expected Maximum Sharpe Ratio (approximate for normal distribution)
        expected_max_sharpe = np.sqrt(var_trials) * ((1 - 0.5772) * stats.norm.ppf(1 - 1.0/n_trials) + 0.5772 * stats.norm.ppf(1 - 1.0/(n_trials * np.e)))
        
        # Adjust Sharpe for skew and kurtosis
        adj_sharpe = sharpe * np.sqrt(sample_size - 1)
        denom = np.sqrt(1 - skew * sharpe + ((kurtosis - 1) / 4) * (sharpe ** 2))
        
        # True probability calculation
        z_score = (adj_sharpe - expected_max_sharpe * np.sqrt(sample_size - 1)) / denom
        return stats.norm.cdf(z_score)

class VectorizedEvaluator:
    """
    Ultra-fast vectorized backtester designed specifically for screening thousands
    of Alpha candidates in the Factory phase. This does NOT replace the event-driven
    M15 backtester.
    """
    def __init__(self, price_data: pd.Series):
        self.price_data = price_data
        self.returns = price_data.pct_change().shift(-1) # Forward returns
        
    def evaluate(self, signals: pd.Series) -> dict:
        """
        Calculates simple vector math for returns.
        signals: continuous or discrete [-1, 1] aligned with price_data index
        """
        strategy_returns = signals * self.returns
        
        # Annualized metrics (assuming daily)
        mean_ret = strategy_returns.mean() * 252
        volatility = strategy_returns.std() * np.sqrt(252)
        
        sharpe = mean_ret / volatility if volatility != 0 else 0
        
        # Turnover approx
        turnover = signals.diff().abs().sum() / len(signals) * 252
        
        skew = stats.skew(strategy_returns.dropna())
        kurtosis = stats.kurtosis(strategy_returns.dropna())
        
        return {
            "sharpe": sharpe,
            "mean_return": mean_ret,
            "volatility": volatility,
            "annual_turnover": turnover,
            "skew": skew,
            "kurtosis": kurtosis,
            "sample_size": len(signals.dropna())
        }
