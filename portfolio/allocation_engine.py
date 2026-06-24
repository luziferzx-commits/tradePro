import pandas as pd
import numpy as np

class AllocationEngine:
    def __init__(self):
        self.regime_multipliers = {
            'LOW_VOL_COMPRESSION': 1.2,
            'NORMAL_VOLATILITY': 1.0,
            'HIGH_VOL_EXPANSION': 0.8
        }
        self.max_kelly = 0.25

    def calculate_weights(self, clusters: dict, hypotheses_stats: dict, regime: str) -> dict:
        """
        Calculates the capital weight for each alpha cluster.
        Weight = RiskParity * StabilityScore * RegimeMultiplier * KellyFraction
        """
        # For each cluster, we pick the most stable alpha as the representative
        # Or we calculate the cluster average stats
        
        cluster_weights = {}
        total_inv_vol = 0.0
        
        # Step 1: Calculate raw components
        for cluster_id, alphas in clusters.items():
            # Representative stat (use max stability in cluster)
            best_alpha = None
            best_stability = -1
            
            for a in alphas:
                stat = hypotheses_stats[a]
                stab = stat['cpcv_consistency'] * stat['tier1_score']
                if stab > best_stability:
                    best_stability = stab
                    best_alpha = a
                    
            stat = hypotheses_stats[best_alpha]
            
            # 1. Stability Score
            stability_score = best_stability
            
            # 2. Kelly Fraction
            win_rate = stat['hit_rate']
            # Assume win/loss ratio is approximated by tail ratio or roughly 1.0 for simplicity if unknown
            # Standard Kelly = W - ((1-W)/R)
            r_ratio = stat.get('tail_ratio', 1.0)
            if r_ratio == 0:
                r_ratio = 1.0
                
            kelly = win_rate - ((1.0 - win_rate) / r_ratio)
            kelly_fraction = min(max(kelly, 0.0), self.max_kelly)
            
            # 3. Risk Parity (Inverse Volatility proxy)
            # We can use historical drawdown or std dev of expected return. 
            # We'll use 1 / Expected Return Volatility (approx using absolute return as risk proxy for now)
            vol_proxy = abs(stat['expected_return']) if stat['expected_return'] != 0 else 0.001
            inv_vol = 1.0 / vol_proxy
            total_inv_vol += inv_vol
            
            cluster_weights[cluster_id] = {
                'representative': best_alpha,
                'stability': stability_score,
                'kelly': kelly_fraction,
                'inv_vol': inv_vol
            }
            
        # Step 2: Final Combination
        final_weights = {}
        regime_mult = self.regime_multipliers.get(regime, 1.0)
        
        for cid, w in cluster_weights.items():
            risk_parity = w['inv_vol'] / total_inv_vol if total_inv_vol > 0 else 0
            
            weight = risk_parity * w['stability'] * regime_mult * w['kelly']
            final_weights[cid] = weight
            
        # Normalize weights so they sum to 1.0 (or less if low confidence)
        total_weight = sum(final_weights.values())
        if total_weight > 0:
            for cid in final_weights:
                final_weights[cid] /= total_weight
                
        return final_weights
