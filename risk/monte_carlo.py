"""risk/monte_carlo.py — Monte Carlo Simulation engine for trade returns."""
import numpy as np

class MonteCarloSimulator:
    @staticmethod
    def simulate(trade_returns: list[float], n_simulations: int = 10000, n_trades: int = 250) -> np.ndarray:
        """
        Simulate equity curves using bootstrap resampling (with replacement).
        :param trade_returns: List of historical trade returns (e.g., in R or percentage).
        :param n_simulations: Number of Monte Carlo paths to generate.
        :param n_trades: Number of future trades per path to simulate.
        :return: 2D numpy array of shape (n_simulations, n_trades) representing cumulative paths.
        """
        if not trade_returns:
            raise ValueError("trade_returns list cannot be empty.")
        
        returns_array = np.array(trade_returns)
        
        # Random choice with replacement
        samples = np.random.choice(returns_array, size=(n_simulations, n_trades), replace=True)
        
        # Calculate cumulative returns over each path
        cumulative_paths = np.cumsum(samples, axis=1)
        
        return cumulative_paths

    @staticmethod
    def calculate_drawdowns(cumulative_paths: np.ndarray) -> np.ndarray:
        """
        Calculates the maximum drawdown for each simulated path.
        Drawdown is measured in the same units as the paths (e.g. R or percentage).
        :param cumulative_paths: 2D array of simulated equity paths.
        :return: 1D array of max drawdowns per path.
        """
        # Calculate running peak
        peaks = np.maximum.accumulate(cumulative_paths, axis=1)
        # Ensure peaks don't drop below 0 (if path starts negative immediately)
        peaks = np.maximum(peaks, 0)
        
        # Drawdown = Running Peak - Current Value
        drawdowns = peaks - cumulative_paths
        
        # Max drawdown per path
        max_drawdowns = np.max(drawdowns, axis=1)
        
        return max_drawdowns
