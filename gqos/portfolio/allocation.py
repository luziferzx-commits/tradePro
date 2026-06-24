from abc import ABC, abstractmethod
from typing import Dict
import pandas as pd
import numpy as np

class ICapitalAllocator(ABC):
    @abstractmethod
    def allocate(self, base_weights: Dict[str, float], returns_df: pd.DataFrame, target_capital: float) -> Dict[str, float]:
        """
        Scales Alpha base weights to target capital allocation.
        """
        pass

class EqualWeightAllocator(ICapitalAllocator):
    def allocate(self, base_weights: Dict[str, float], returns_df: pd.DataFrame, target_capital: float) -> Dict[str, float]:
        n = len(base_weights)
        if n == 0: return {}
        weight = target_capital / n
        return {k: weight for k in base_weights.keys()}

class FractionalKellyAllocator(ICapitalAllocator):
    def __init__(self, fraction: float = 0.5, risk_free_rate: float = 0.0):
        self.fraction = fraction
        self.risk_free_rate = risk_free_rate
        
    def allocate(self, base_weights: Dict[str, float], returns_df: pd.DataFrame, target_capital: float) -> Dict[str, float]:
        """
        Approximates Kelly for each Alpha independently, then scales the total 
        using the fractional Kelly multiplier.
        f = (mu - r) / sigma^2
        """
        allocations = {}
        for alpha_id, b_weight in base_weights.items():
            if alpha_id not in returns_df.columns:
                continue
                
            rets = returns_df[alpha_id]
            mu = rets.mean() * 252 # Annualized
            var = rets.var() * 252
            
            if var == 0:
                allocations[alpha_id] = 0.0
            else:
                f_opt = (mu - self.risk_free_rate) / var
                # Apply fraction
                f_frac = f_opt * self.fraction
                # Cap leverage per alpha for safety
                f_frac = max(0.0, min(f_frac, 2.0)) 
                
                # Multiply by the base weight (e.g. from HRP)
                allocations[alpha_id] = f_frac * b_weight * target_capital
                
        return allocations
