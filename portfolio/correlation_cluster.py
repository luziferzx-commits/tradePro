import pandas as pd
import numpy as np
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

class CorrelationCluster:
    @staticmethod
    def calculate_distance_matrix(strategy_returns: pd.DataFrame, signal_masks: pd.DataFrame, regime_masks: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates the 3-Layer Correlation System:
        Layer A: Return Correlation
        Layer B: Signal Overlap (Jaccard)
        Layer C: Regime Overlap
        """
        cols = strategy_returns.columns
        n = len(cols)
        dist_matrix = np.zeros((n, n))
        
        # Layer A: Return Correlation (Pearson)
        ret_corr = strategy_returns.corr().fillna(0).values
        
        # Layer B & C: Calculate pairwise
        for i in range(n):
            for j in range(i, n):
                if i == j:
                    dist_matrix[i, j] = 0.0
                    continue
                    
                # Layer B: Signal Correlation (Jaccard similarity of entry signals)
                sig_i = signal_masks[cols[i]].values
                sig_j = signal_masks[cols[j]].values
                
                intersection = np.sum(sig_i & sig_j)
                union = np.sum(sig_i | sig_j)
                sig_corr = intersection / union if union > 0 else 0.0
                
                # Layer C: Regime Overlap (Similarity of active regimes)
                reg_i = regime_masks[cols[i]].values
                reg_j = regime_masks[cols[j]].values
                reg_intersection = np.sum(reg_i & reg_j)
                reg_union = np.sum(reg_i | reg_j)
                reg_corr = reg_intersection / reg_union if reg_union > 0 else 0.0
                
                # Composite Correlation
                # Give weight: 50% Returns, 30% Signal, 20% Regime
                comp_corr = 0.5 * ret_corr[i, j] + 0.3 * sig_corr + 0.2 * reg_corr
                
                # Distance = 1 - correlation (for clustering)
                dist = 1.0 - comp_corr
                dist_matrix[i, j] = dist
                dist_matrix[j, i] = dist
                
        return pd.DataFrame(dist_matrix, index=cols, columns=cols)

    @staticmethod
    def cluster_alphas(dist_matrix: pd.DataFrame, threshold: float = 0.3) -> dict:
        """
        Groups alphas into redundant clusters based on the distance matrix.
        Threshold = 0.3 means grouping elements with correlation > 0.7
        """
        print("--- Running 3-Layer Correlation Clustering ---")
        # Ensure symmetric zero-diagonal
        dist_array = dist_matrix.values.copy()
        np.fill_diagonal(dist_array, 0)
        
        # scipy linkage requires condensed distance matrix
        condensed_dist = squareform(dist_array, checks=False)
        
        Z = linkage(condensed_dist, method='complete')
        
        # Extract flat clusters
        labels = fcluster(Z, t=threshold, criterion='distance')
        
        clusters = {}
        for i, col in enumerate(dist_matrix.columns):
            cluster_id = labels[i]
            if cluster_id not in clusters:
                clusters[cluster_id] = []
            clusters[cluster_id].append(col)
            
        print(f"Reduced {len(dist_matrix.columns)} raw alphas into {len(clusters)} distinct clusters.")
        return clusters
