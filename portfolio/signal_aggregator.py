import pandas as pd
import numpy as np

class SignalAggregator:
    def __init__(self, hypotheses_stats: dict):
        """
        hypotheses_stats: dict mapping alpha_name to its stats:
        {
            'ALPHA_1_...': {
                'expected_return': 0.005,
                'hit_rate': 0.55,
                'cpcv_consistency': 0.9,
                'tier1_score': 1.0,
                'direction': 1
            }
        }
        """
        self.stats = hypotheses_stats
        self.alpha_scores = {}
        for name, stat in self.stats.items():
            # AlphaScore = expected_return * probability * stability
            stability = stat['cpcv_consistency'] * stat['tier1_score']
            score = abs(stat['expected_return']) * stat['hit_rate'] * stability
            self.alpha_scores[name] = score

    def resolve_conflicts(self, active_signals: dict) -> float:
        """
        active_signals: dict mapping alpha_name -> direction (+1, -1) active at time t.
        Returns a net confidence score between -1 and 1.
        """
        if not active_signals:
            return 0.0
            
        buy_score = 0.0
        sell_score = 0.0
        
        for name, direction in active_signals.items():
            score = self.alpha_scores.get(name, 0.0)
            if direction == 1:
                buy_score += score
            elif direction == -1:
                sell_score += score
                
        # CASE A: Opposite Signals (Conflict)
        if buy_score > 0 and sell_score > 0:
            if buy_score > sell_score * 1.5:
                # Clear Winner (Buy)
                return buy_score / (buy_score + sell_score)
            elif sell_score > buy_score * 1.5:
                # Clear Winner (Sell)
                return -sell_score / (buy_score + sell_score)
            else:
                # CASE C: Low confidence conflict
                # Reduce exposure severely, do not net blindly
                return (buy_score - sell_score) * 0.1
                
        # CASE B: Same Direction
        if buy_score > 0:
            # Conviction Buy
            return min(1.0, buy_score * 1000) # Scaling factor depends on absolute score sizes
        if sell_score > 0:
            # Conviction Sell
            return max(-1.0, -sell_score * 1000)
            
        return 0.0
        
    def aggregate_timeline(self, df_signals: pd.DataFrame) -> pd.Series:
        """
        Takes a dataframe where columns are alpha names and values are active signals (+1, 0, -1).
        Returns a series of daily net positions.
        """
        print("--- Aggregating Signals & Resolving Conflicts ---")
        net_positions = np.zeros(len(df_signals))
        
        # Determine scaling factor dynamically based on max score
        max_score = max(self.alpha_scores.values()) if self.alpha_scores else 1.0
        scaling_factor = 1.0 / (max_score * 3) if max_score > 0 else 1.0
        
        for i in range(len(df_signals)):
            row = df_signals.iloc[i]
            active = {col: val for col, val in row.items() if val != 0}
            
            if not active:
                continue
                
            buy_score = sum(self.alpha_scores[col] for col, val in active.items() if val == 1)
            sell_score = sum(self.alpha_scores[col] for col, val in active.items() if val == -1)
            
            if buy_score > 0 and sell_score > 0:
                if buy_score > sell_score * 1.5:
                    net_positions[i] = min(1.0, buy_score * scaling_factor)
                elif sell_score > buy_score * 1.5:
                    net_positions[i] = max(-1.0, -sell_score * scaling_factor)
                else:
                    net_positions[i] = (buy_score - sell_score) * scaling_factor * 0.1
            elif buy_score > 0:
                net_positions[i] = min(1.0, buy_score * scaling_factor)
            elif sell_score > 0:
                net_positions[i] = max(-1.0, -sell_score * scaling_factor)
                
        return pd.Series(net_positions, index=df_signals.index)
