import numpy as np
import pandas as pd
from typing import Optional
from statsmodels.tsa.stattools import adfuller

class FractionalDifferentiation:
    @staticmethod
    def get_weights(d: float, size: int) -> np.ndarray:
        """
        Returns the weights for fractional differentiation.
        w[0] = 1
        w[k] = -w[k-1] * (d - k + 1) / k
        """
        w = [1.0]
        for k in range(1, size):
            w_k = -w[-1] / k * (d - k + 1)
            w.append(w_k)
        return np.array(w[::-1]).reshape(-1, 1) # Reverse to align with chronological data

    @staticmethod
    def get_weights_ffd(d: float, thres: float = 1e-5) -> np.ndarray:
        """
        Calculates weights until they drop below the given threshold (Truncated Fixed Window).
        """
        w = [1.0]
        k = 1
        while True:
            w_k = -w[-1] / k * (d - k + 1)
            if abs(w_k) < thres:
                break
            w.append(w_k)
            k += 1
        return np.array(w[::-1]).reshape(-1, 1)
        
    @staticmethod
    def frac_diff_ffd(series: pd.Series, d: float, thres: float = 1e-5) -> pd.Series:
        """
        Applies Fixed-Window Truncated Fractional Differentiation.
        """
        weights = FractionalDifferentiation.get_weights_ffd(d, thres)
        width = len(weights) - 1
        
        df = pd.Series(index=series.index, dtype=float)
        
        for i in range(width, len(series)):
            window = series.iloc[i-width : i+1].values.reshape(-1, 1)
            df.iloc[i] = np.dot(weights.T, window)[0, 0]
            
        return df

class AutoFD:
    @staticmethod
    def select_d(series: pd.Series, max_d: float = 1.0, step: float = 0.05, thres: float = 1e-5, p_value: float = 0.05) -> float:
        """
        Iteratively tests values of d to find the lowest d that makes the series stationary (via ADF test).
        """
        out = pd.DataFrame(columns=['adfStat', 'pVal', 'lags', 'nObs', '95% conf', 'corr'])
        d_vals = np.arange(0, max_d, step)
        
        min_d = max_d
        
        for d in d_vals:
            diff_series = FractionalDifferentiation.frac_diff_ffd(series, d, thres).dropna()
            if len(diff_series) < 10:
                continue
                
            res = adfuller(diff_series, maxlag=1, regression='c', autolag=None)
            pval = res[1]
            
            if pval < p_value:
                min_d = d
                break
                
        return min_d
