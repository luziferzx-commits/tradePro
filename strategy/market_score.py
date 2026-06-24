import pandas as pd
from datetime import datetime
from strategy.setups import SetupEvaluator

class MarketScoreCalculator:
    @staticmethod
    def calculate(df: pd.DataFrame, regime: dict) -> dict:
        if df.empty:
            return {"final_score": 0.0, "final_direction": "NEUTRAL"}
            
        setups = SetupEvaluator.evaluate_all(df, regime)
        
        if not setups:
            return {"final_score": 0.0, "final_direction": "NEUTRAL", "setup_name": "None", "reason": "No data"}
            
        # Anti-overlap rule: choose the highest scoring setup
        best_setup = max(setups, key=lambda s: s['score'])
        
        # We need to format the return dict to be compatible with existing code
        return {
            "final_direction": best_setup['direction'],
            "final_score": float(best_setup['score']),
            "setup_name": best_setup['setup_name'],
            "reason": best_setup['reason'],
            "all_setups": setups
        }
        

