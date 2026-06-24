import numpy as np
import pandas as pd
from typing import List, Tuple

from gqos.research.statistics.bootstrap import BootstrapEngine

class FalseDiscoveryRate:
    @staticmethod
    def benjamini_hochberg(p_values: np.ndarray, alpha: float = 0.05) -> np.ndarray:
        """
        Applies the Benjamini-Hochberg procedure to control the False Discovery Rate.
        Returns a boolean array indicating which tests reject the null hypothesis (True = Discoveries).
        """
        n = len(p_values)
        sorted_indices = np.argsort(p_values)
        sorted_p = p_values[sorted_indices]
        
        # Calculate B-H critical values
        critical_values = (np.arange(1, n + 1) / n) * alpha
        
        # Find the largest k where p_k <= critical_value_k
        reject = sorted_p <= critical_values
        if not np.any(reject):
            return np.zeros(n, dtype=bool)
            
        max_k = np.max(np.where(reject)[0])
        
        # Reject all H_0 for i=1,...,max_k
        results = np.zeros(n, dtype=bool)
        results[sorted_indices[:max_k + 1]] = True
        
        return results

class RealityCheck:
    @staticmethod
    def white_reality_check(strategy_returns: pd.DataFrame, benchmark_returns: pd.Series, num_bootstraps: int = 1000, seed: int = None) -> float:
        """
        White's Reality Check for data snooping.
        Tests H0: The best strategy does not outperform the benchmark.
        Returns the p-value.
        """
        n_obs = len(benchmark_returns)
        
        # Calculate excess returns relative to benchmark
        excess_returns = strategy_returns.sub(benchmark_returns, axis=0)
        mean_excess = excess_returns.mean().values
        
        # Test statistic: max mean excess return
        v_star = np.max(mean_excess)
        
        # Bootstrap
        indices = BootstrapEngine.stationary_bootstrap(n_obs, num_bootstraps, seed=seed)
        v_star_b = np.zeros(num_bootstraps)
        
        excess_arr = excess_returns.values
        
        for i in range(num_samples := num_bootstraps):
            # Bootstrapped excess returns, centered around original sample mean to enforce H0
            centered_boot_excess = excess_arr[indices[i]] - mean_excess
            boot_mean = np.mean(centered_boot_excess, axis=0)
            v_star_b[i] = np.max(boot_mean)
            
        # p-value is the fraction of bootstrapped max means that exceed the original max mean
        p_val = np.sum(v_star_b >= v_star) / num_bootstraps
        return p_val

class SuperiorPredictiveAbility:
    @staticmethod
    def hansen_spa(strategy_returns: pd.DataFrame, benchmark_returns: pd.Series, num_bootstraps: int = 1000, seed: int = None) -> float:
        """
        Hansen's Superior Predictive Ability (SPA) test.
        Less conservative than White's RC by re-centering poor models to zero.
        Returns the p-value.
        """
        n_obs = len(benchmark_returns)
        excess_returns = strategy_returns.sub(benchmark_returns, axis=0)
        mean_excess = excess_returns.mean().values
        std_excess = excess_returns.std().values
        
        v_star = np.max(mean_excess)
        
        indices = BootstrapEngine.stationary_bootstrap(n_obs, num_bootstraps, seed=seed)
        v_star_b = np.zeros(num_bootstraps)
        
        excess_arr = excess_returns.values
        
        # Hansen's re-centering parameter
        g_bar = mean_excess.copy()
        threshold = np.sqrt((std_excess ** 2) / n_obs * 2 * np.log(np.log(n_obs)))
        g_bar[mean_excess <= -threshold] = 0 # Re-center poor models to 0
        
        for i in range(num_bootstraps):
            boot_excess = excess_arr[indices[i]]
            boot_mean = np.mean(boot_excess, axis=0)
            # Center and add back the adjusted mean
            adjusted_boot_mean = boot_mean - mean_excess + g_bar
            v_star_b[i] = np.max(adjusted_boot_mean)
            
        p_val = np.sum(v_star_b >= v_star) / num_bootstraps
        return p_val
