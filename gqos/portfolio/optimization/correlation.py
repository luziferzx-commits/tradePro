import pandas as pd
import numpy as np
from abc import ABC, abstractmethod

class ICorrelationEstimator(ABC):
    @abstractmethod
    def estimate(self, returns_df: pd.DataFrame) -> pd.DataFrame:
        """
        Estimates the correlation matrix for a DataFrame of Alpha returns.
        """
        pass

class PearsonCorrelation(ICorrelationEstimator):
    def estimate(self, returns_df: pd.DataFrame) -> pd.DataFrame:
        return returns_df.corr(method='pearson')

class SpearmanCorrelation(ICorrelationEstimator):
    def estimate(self, returns_df: pd.DataFrame) -> pd.DataFrame:
        return returns_df.corr(method='spearman')

class DistanceCorrelation(ICorrelationEstimator):
    def estimate(self, returns_df: pd.DataFrame) -> pd.DataFrame:
        """
        Distance correlation captures non-linear dependencies.
        Simplified placeholder: In production, requires dcor library.
        Falling back to spearman for this interface if dcor is missing.
        """
        try:
            import dcor
            # dcor.distance_correlation is pairwise
            cols = returns_df.columns
            n = len(cols)
            mat = np.zeros((n, n))
            for i in range(n):
                for j in range(n):
                    if i == j:
                        mat[i, j] = 1.0
                    else:
                        mat[i, j] = dcor.distance_correlation(returns_df[cols[i]], returns_df[cols[j]])
            return pd.DataFrame(mat, index=cols, columns=cols)
        except ImportError:
            # Fallback
            return returns_df.corr(method='spearman')
