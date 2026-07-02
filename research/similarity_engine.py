import pandas as pd
import numpy as np

class SimilarityEngine:
    def __init__(self, query_engine):
        self.qe = query_engine

    def encode_bucket(self, b_type, val):
        val = str(val).lower()
        if b_type == 'atr' or b_type == 'volatility':
            mapping = {'low': 1, 'medium': 2, 'high': 3, 'extreme': 4}
            for k, v in mapping.items():
                if k in val: return v
            return 2
        elif b_type == 'adx':
            mapping = {'weak': 1, 'rising': 2, 'strong': 3, 'extreme': 4}
            for k, v in mapping.items():
                if k in val: return v
            return 2
        elif b_type == 'trend':
            mapping = {'strong down': 1, 'down': 2, 'flat': 3, 'up': 4, 'strong up': 5}
            for k, v in mapping.items():
                if k in val: return v
            return 3
        return 0

    def find_similar_patterns(self, live_features: dict, direction: str, threshold: float = 0.80):
        df = self.qe.cache.df
        if df is None or df.empty: return None

        # Hard filters
        mask = (df['symbol'] == live_features['symbol']) & \
               (df['session_label'] == live_features['session_label']) & \
               (df['regime'] == live_features['regime']) & \
               (df['direction'] == direction)
               
        candidates = df[mask].copy()
        if candidates.empty: return None

        live_atr_enc = self.encode_bucket('atr', live_features.get('atr_bucket', ''))
        live_adx_enc = self.encode_bucket('adx', live_features.get('adx_bucket', ''))
        live_trend_enc = self.encode_bucket('trend', live_features.get('trend_bucket', ''))

        def calc_distance(row):
            atr_e = self.encode_bucket('atr', row['atr_bucket'])
            adx_e = self.encode_bucket('adx', row['adx_bucket'])
            trend_e = self.encode_bucket('trend', row['trend_bucket'])
            
            # Max possible distance per feature is ~4. Normalize to 0-1.
            d_atr = abs(atr_e - live_atr_enc) / 3.0
            d_adx = abs(adx_e - live_adx_enc) / 3.0
            d_trend = abs(trend_e - live_trend_enc) / 4.0
            
            # Weighted distance
            w_atr, w_adx, w_trend = 1.0, 1.0, 1.5
            total_w = w_atr + w_adx + w_trend
            
            dist = (d_atr * w_atr + d_adx * w_adx + d_trend * w_trend) / total_w
            return 1.0 - dist # Return similarity (1.0 is exact match)

        candidates['similarity_score'] = candidates.apply(calc_distance, axis=1)
        candidates = candidates[candidates['similarity_score'] >= threshold]
        
        if candidates.empty: return None
        
        candidates['evidence_score'] = candidates['similarity_score'] * (candidates['profit_factor'] / 2.0)
        
        # Aggregate stats
        agg_pf = (candidates['profit_factor'] * candidates['occurrences']).sum() / candidates['occurrences'].sum()
        agg_exp = (candidates['expectancy_r'] * candidates['occurrences']).sum() / candidates['occurrences'].sum()
        agg_win = (candidates['win_rate'] * candidates['occurrences']).sum() / candidates['occurrences'].sum()
        total_n = candidates['occurrences'].sum()
        
        best = candidates.sort_values('evidence_score', ascending=False).iloc[0]
        
        return {
            "nearest_pattern": best.to_dict(),
            "promotions": candidates['promotion_status'].tolist(),
            "aggregate_pf": round(agg_pf, 2),
            "aggregate_expectancy_r": round(agg_exp, 2),
            "aggregate_win_rate": round(agg_win, 2),
            "sample_size": int(total_n),
            "similarity_score": round(best['similarity_score'], 2),
            "evidence_score": round(best['evidence_score'], 2)
        }
