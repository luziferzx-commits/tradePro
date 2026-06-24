import numpy as np
from typing import Callable, List, Tuple
import pandas as pd

class BootstrapEngine:
    """
    Centralized engine for stationary bootstrap resampling.
    Used by White's Reality Check, SPA, and PBO.
    """
    @staticmethod
    def stationary_bootstrap(data_length: int, num_samples: int, block_size: float = 0.1, seed: int = None) -> np.ndarray:
        """
        Generates indices for stationary bootstrap (Politis and Romano 1994).
        Returns a matrix of shape (num_samples, data_length) containing indices.
        """
        if seed is not None:
            np.random.seed(seed)
            
        indices = np.zeros((num_samples, data_length), dtype=int)
        p = 1.0 / (data_length * block_size) # Probability of starting a new block
        
        for i in range(num_samples):
            idx = np.random.randint(0, data_length)
            for j in range(data_length):
                indices[i, j] = idx
                if np.random.random() < p:
                    idx = np.random.randint(0, data_length)
                else:
                    idx = (idx + 1) % data_length
                    
        return indices
