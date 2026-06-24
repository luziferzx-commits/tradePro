import numpy as np
import scipy.stats as stats

class InstitutionalMetrics:
    @staticmethod
    def expected_max_sharpe(trial_sharpes: np.ndarray) -> float:
        """
        Calculates the Expected Maximum Sharpe Ratio (EMS) for a given set of independent trials.
        Used to determine if the observed max Sharpe is surprisingly high or just expected due to multiple testing.
        """
        n_trials = len(trial_sharpes)
        if n_trials <= 1:
            return trial_sharpes[0] if n_trials == 1 else 0.0
            
        var_trials = np.var(trial_sharpes)
        std_trials = np.sqrt(var_trials)
        
        euler_mascheroni = 0.5772156649
        
        # Approximation for normal distribution
        expected_max = std_trials * ((1 - euler_mascheroni) * stats.norm.ppf(1 - 1.0/n_trials) + euler_mascheroni * stats.norm.ppf(1 - 1.0/(n_trials * np.e)))
        
        return expected_max

    @staticmethod
    def min_track_record_length(sharpe: float, skew: float = 0.0, kurtosis: float = 3.0, target_sharpe: float = 0.0, confidence_level: float = 0.95) -> float:
        """
        Calculates the Minimum Track Record Length (MTL).
        This is the minimum number of observations (e.g., years) required to prove that the strategy's
        Sharpe Ratio is significantly greater than the target_sharpe at the given confidence level.
        """
        if sharpe <= target_sharpe:
            return float('inf') # Impossible to prove it's better if it's already worse
            
        z_alpha = stats.norm.ppf(confidence_level)
        
        # Variance of the Sharpe ratio estimate
        var_sharpe_hat = 1 + (0.5 * (sharpe ** 2)) - (skew * sharpe) + (((kurtosis - 3) / 4) * (sharpe ** 2))
        
        # Required length
        mtl = var_sharpe_hat * ((z_alpha / (sharpe - target_sharpe)) ** 2)
        
        return mtl
