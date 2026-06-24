import pandas as pd
import numpy as np
from typing import Dict, List, Optional

class AlphaMatrix:
    @staticmethod
    def cross_model_correlation(forecasts: Dict[str, pd.Series], method: str = 'spearman') -> pd.DataFrame:
        """
        Calculates the correlation matrix between multiple alpha models.
        method: 'spearman' (default for alphas) or 'pearson'
        """
        if not forecasts:
            return pd.DataFrame()
            
        df = pd.DataFrame(forecasts).fillna(0.0)
        return df.corr(method=method)

    @staticmethod
    def orthogonalize(target: pd.Series, base: pd.Series) -> pd.Series:
        """
        Gram-Schmidt Orthogonalization.
        Removes the linear projection of `base` from `target`.
        Returns the residual target alpha that is orthogonal (uncorrelated) to `base`.
        """
        # Align series
        df = pd.concat([target, base], axis=1).dropna()
        if len(df) == 0:
            return pd.Series()
            
        y = df.iloc[:, 0].values
        x = df.iloc[:, 1].values
        
        dot_xx = np.dot(x, x)
        if dot_xx == 0:
            return pd.Series(y, index=df.index)
            
        dot_yx = np.dot(y, x)
        projection = (dot_yx / dot_xx) * x
        
        residual = y - projection
        
        return pd.Series(residual, index=df.index)
