import pandas as pd
import numpy as np
import scipy.cluster.hierarchy as sch
from scipy.spatial.distance import squareform
from typing import Dict, List

from gqos.portfolio.optimization.correlation import ICorrelationEstimator, PearsonCorrelation

class HierarchicalRiskParity:
    def __init__(self, correlation_estimator: ICorrelationEstimator = None):
        self.corr_estimator = correlation_estimator or PearsonCorrelation()
        self.linkage_matrix = None
        
    def _get_quasi_diag(self, link: np.ndarray) -> List[int]:
        """
        Sort clustered items by distance.
        """
        link = link.astype(int)
        sort_ix = pd.Series([link[-1, 0], link[-1, 1]])
        num_items = link[-1, 3]
        
        while sort_ix.max() >= num_items:
            sort_ix.index = range(0, sort_ix.shape[0] * 2, 2) # make space
            df0 = sort_ix[sort_ix >= num_items]
            i = df0.index
            j = df0.values - num_items
            sort_ix[i] = link[j, 0] # item 1
            df0 = pd.Series(link[j, 1], index=i + 1)
            sort_ix = pd.concat([sort_ix, df0])
            sort_ix = sort_ix.sort_index()
            sort_ix.index = range(sort_ix.shape[0])
            
        return sort_ix.tolist()

    def _get_rec_bipart(self, cov: pd.DataFrame, sort_ix: List[int]) -> pd.Series:
        """
        Compute HRP allocation recursively.
        """
        w = pd.Series(1.0, index=sort_ix)
        c_items = [sort_ix]
        
        while len(c_items) > 0:
            c_items = [i[j:k] for i in c_items for j, k in ((0, len(i) // 2), (len(i) // 2, len(i))) if len(i) > 1]
            for i in range(0, len(c_items), 2):
                c_items0 = c_items[i] # cluster 1
                c_items1 = c_items[i+1] # cluster 2
                
                c_var0 = self._get_cluster_var(cov, c_items0)
                c_var1 = self._get_cluster_var(cov, c_items1)
                
                alpha = 1 - c_var0 / (c_var0 + c_var1)
                
                w[c_items0] *= alpha
                w[c_items1] *= 1 - alpha
                
        return w
        
    def _get_cluster_var(self, cov: pd.DataFrame, c_items: List[int]) -> float:
        """
        Compute variance of a cluster.
        """
        cov_slice = cov.iloc[c_items, c_items]
        # Inverse variance allocation
        iv = 1.0 / np.diag(cov_slice)
        iv /= iv.sum()
        w = iv.reshape(-1, 1)
        c_var = np.dot(np.dot(w.T, cov_slice), w)[0, 0]
        return c_var

    def optimize(self, returns_df: pd.DataFrame) -> Dict[str, float]:
        """
        Returns optimal HRP weights for the given returns.
        """
        corr = self.corr_estimator.estimate(returns_df)
        cov = returns_df.cov()
        
        # Distance matrix
        dist = np.sqrt(0.5 * (1 - corr).clip(0, 1))
        
        # Linkage clustering
        dist_array = squareform(dist.values, checks=False)
        self.linkage_matrix = sch.linkage(dist_array, method='single')
        
        sort_ix = self._get_quasi_diag(self.linkage_matrix)
        
        # HRP weights
        weights = self._get_rec_bipart(cov, sort_ix)
        weights.index = returns_df.columns[weights.index]
        
        return weights.to_dict()
