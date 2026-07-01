import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

class SRDetector:
    @staticmethod
    def detect_zones(df: pd.DataFrame, window: int = 15, threshold_pct: float = 0.001) -> dict:
        """
        Detects Support and Resistance zones using local rolling max/min.
        df: The higher timeframe dataframe (e.g. H4 or H1).
        window: the rolling window size to find peaks/valleys.
        threshold_pct: percentage distance to cluster nearby levels.
        
        Returns:
            {
                "resistances": [float, float, ...], # sorted descending
                "supports": [float, float, ...] # sorted descending
            }
        """
        if df is None or len(df) < window * 2:
            return {"resistances": [], "supports": []}
            
        highs = df['high'].values
        lows = df['low'].values
        
        resistances = []
        supports = []
        
        # Find local peaks
        for i in range(window, len(df) - window):
            if highs[i] == np.max(highs[i-window:i+window+1]):
                resistances.append(highs[i])
            if lows[i] == np.min(lows[i-window:i+window+1]):
                supports.append(lows[i])
                
        # Cluster them to remove duplicates too close to each other
        def cluster_levels(levels):
            if not levels: return []
            levels = sorted(levels, reverse=True)
            clustered = []
            current_cluster = [levels[0]]
            for lvl in levels[1:]:
                avg = sum(current_cluster) / len(current_cluster)
                if abs(lvl - avg) / avg < threshold_pct:
                    current_cluster.append(lvl)
                else:
                    clustered.append(sum(current_cluster) / len(current_cluster))
                    current_cluster = [lvl]
            if current_cluster:
                clustered.append(sum(current_cluster) / len(current_cluster))
            return clustered

        res_zones = cluster_levels(resistances)
        sup_zones = cluster_levels(supports)
        
        return {
            "resistances": sorted(res_zones, reverse=True),
            "supports": sorted(sup_zones, reverse=True)
        }

    @staticmethod
    def evaluate_sr_proximity(current_price: float, zones: dict, direction: str, min_distance_pct: float = 0.0015):
        """
        Checks if the current price is dangerously close to a major S/R zone.
        direction: "LONG" or "SHORT".
        min_distance_pct: e.g. 0.0015 is 0.15% (For Gold at 2300, it's 3.45. For EURUSD at 1.08, it's 16 pips).
        
        Returns: 
           (is_danger, nearest_level, distance_pct)
        """
        if direction == "LONG":
            # Look for resistances ABOVE current price
            above = [r for r in zones.get("resistances", []) if r > current_price]
            if not above:
                return False, 0.0, 999.0
            nearest = min(above)
            dist_pct = (nearest - current_price) / current_price
            return dist_pct < min_distance_pct, nearest, dist_pct
            
        elif direction == "SHORT":
            # Look for supports BELOW current price
            below = [s for s in zones.get("supports", []) if s < current_price]
            if not below:
                return False, 0.0, 999.0
            nearest = max(below)
            dist_pct = (current_price - nearest) / current_price
            return dist_pct < min_distance_pct, nearest, dist_pct
            
        return False, 0.0, 999.0
