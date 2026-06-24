import pandas as pd
import numpy as np
from typing import Dict

class PortfolioStressTest:
    """
    Subjects the target portfolio allocation to various market shocks.
    """
    @staticmethod
    def apply_shock(allocations: Dict[str, float], returns_df: pd.DataFrame, scenario: str) -> float:
        """
        Returns the expected portfolio drawdown under the given scenario.
        """
        if not allocations:
            return 0.0
            
        alphas = list(allocations.keys())
        weights = np.array([allocations[a] for a in alphas])
        # Normalize weights for return calculation
        total_w = np.sum(np.abs(weights))
        if total_w == 0: return 0.0
        w_norm = weights / total_w
        
        cov = returns_df[alphas].cov() * 252
        
        if scenario == "volatility_x2":
            cov_shock = cov * 4 # Var is Vol^2
            port_var = np.dot(w_norm.T, np.dot(cov_shock, w_norm))
            return -np.sqrt(port_var) # 1 stdev shock
            
        elif scenario == "correlation_1":
            # Set all off-diagonal correlations to 1
            stdevs = np.sqrt(np.diag(cov))
            cov_shock = np.outer(stdevs, stdevs)
            port_var = np.dot(w_norm.T, np.dot(cov_shock, w_norm))
            return -np.sqrt(port_var)
            
        elif scenario == "liquidity_shock":
            # Assume 2x slippage/spread cost on turnover
            return -0.05 # Placeholder fixed shock for liquidity gap
            
        elif scenario == "gap_risk":
            # Simulate a 10% market gap down
            # Beta to market would be needed here, assuming 1 for now
            return -0.10
            
        return 0.0
