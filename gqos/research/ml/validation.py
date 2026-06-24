import numpy as np
import pandas as pd
from typing import Iterator, Tuple

class PurgedKFold:
    """
    Purged K-Fold Cross Validation for Financial Time Series.
    Eliminates train/test overlap and enforces an embargo period after the test set
    to prevent forward-looking leakage.
    """
    def __init__(self, n_splits: int = 5, purge_pct: float = 0.01, embargo_pct: float = 0.01):
        self.n_splits = n_splits
        self.purge_pct = purge_pct
        self.embargo_pct = embargo_pct

    def split(self, X: pd.DataFrame, y: pd.Series = None) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        n_samples = len(X)
        indices = np.arange(n_samples)
        
        test_size = n_samples // self.n_splits
        purge_size = int(n_samples * self.purge_pct)
        embargo_size = int(n_samples * self.embargo_pct)
        
        for i in range(self.n_splits):
            test_start = i * test_size
            test_end = (i + 1) * test_size if i < self.n_splits - 1 else n_samples
            
            test_indices = indices[test_start:test_end]
            
            train_indices = []
            
            # Left train set (before test set) - Apply purge
            if test_start > 0:
                left_train_end = max(0, test_start - purge_size)
                train_indices.extend(indices[0:left_train_end])
                
            # Right train set (after test set) - Apply embargo
            if test_end < n_samples:
                right_train_start = min(n_samples, test_end + embargo_size)
                train_indices.extend(indices[right_train_start:])
                
            train_indices = np.array(train_indices)
            
            # Defensive check
            if len(np.intersect1d(train_indices, test_indices)) > 0:
                raise ValueError("Leakage detected: overlap between train and test indices")
                
            yield train_indices, test_indices

def get_standard_kfold():
    raise NotImplementedError("Standard K-Fold is strictly prohibited in financial ML due to leakage. Use PurgedKFold.")

import itertools
from dataclasses import dataclass

@dataclass(frozen=True)
class ValidationManifest:
    dataset_hash: str
    feature_hash: str
    auto_fd_d: float
    tbm_config: dict
    cpcv_config: dict
    bootstrap_seed: int
    pbo: float = 0.0
    dsr: float = 0.0
    spa_p_value: float = 0.0
    reality_check_p_value: float = 0.0

class CombinatorialPurgedCV:
    """
    Combinatorial Purged Cross Validation (CPCV)
    Splits data into N groups. Test sets are formed by taking all combinations of k groups.
    Generates simulated backtest paths to evaluate the Probability of Backtest Overfitting (PBO).
    """
    def __init__(self, n_groups: int = 6, k_test_groups: int = 2, purge_pct: float = 0.01, embargo_pct: float = 0.01):
        self.n_groups = n_groups
        self.k_test_groups = k_test_groups
        self.purge_pct = purge_pct
        self.embargo_pct = embargo_pct
        
    def split(self, X: pd.DataFrame) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        n_samples = len(X)
        indices = np.arange(n_samples)
        
        group_size = n_samples // self.n_groups
        groups = []
        for i in range(self.n_groups):
            start = i * group_size
            end = (i + 1) * group_size if i < self.n_groups - 1 else n_samples
            groups.append(indices[start:end])
            
        purge_size = int(n_samples * self.purge_pct)
        embargo_size = int(n_samples * self.embargo_pct)
        
        combinations = list(itertools.combinations(range(self.n_groups), self.k_test_groups))
        
        for comb in combinations:
            test_indices = np.concatenate([groups[i] for i in comb])
            train_indices = []
            
            for i in range(self.n_groups):
                if i in comb:
                    continue
                    
                # Need to check if this training group is adjacent to any test group
                # Simplified: apply purge and embargo to the whole train group relative to all test indices
                group_idx = groups[i].copy()
                
                # Exclude purged (left of test) and embargoed (right of test)
                valid = np.ones(len(group_idx), dtype=bool)
                for t_idx in test_indices:
                    # Purge (train is before test)
                    valid &= ~((group_idx >= t_idx - purge_size) & (group_idx <= t_idx))
                    # Embargo (train is after test)
                    valid &= ~((group_idx >= t_idx) & (group_idx <= t_idx + embargo_size))
                    
                train_indices.extend(group_idx[valid])
                
            train_indices = np.array(train_indices)
            yield train_indices, test_indices
