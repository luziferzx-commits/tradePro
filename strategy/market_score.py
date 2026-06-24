import pandas as pd
from datetime import datetime
from strategy.factory import StrategyFactory

class MarketScoreCalculator:
    @staticmethod
    def calculate(df: pd.DataFrame, regime: dict, h4_trend: str = "NEUTRAL", asset_class: str = "FOREX") -> dict:
        if df.empty or len(df) < 5:
            return {
                "final_score": 0.0, "final_direction": "NEUTRAL", "setup_name": "None", "reason": "No data", "all_setups": [],
                "trend_score": 0.0, "breakout_score": 0.0, "reversal_score": 0.0, "session_score": 0.0, "h4_trend": h4_trend
            }
            
        evaluator = StrategyFactory.get_evaluator(asset_class)
        setups = evaluator.evaluate_all(df, regime, h4_trend=h4_trend)
        
        if not setups:
            return {
                "final_score": 0.0, "final_direction": "NEUTRAL", "setup_name": "None", "reason": "No data", "all_setups": [],
                "trend_score": 0.0, "breakout_score": 0.0, "reversal_score": 0.0, "session_score": 0.0, "h4_trend": h4_trend
            }
            
        # Anti-overlap rule: choose the highest scoring setup
        best_setup = max(setups, key=lambda s: s['score'])
        
        # Extract component scores
        trend_score = 0.0
        breakout_score = 0.0
        reversal_score = 0.0
        
        for s in setups:
            if s['setup_name'] == "EMA Pullback Continuation":
                trend_score = float(s['score'])
            elif s['setup_name'] in ["London Breakout", "NY Breakout", "Volatility Expansion Breakout"]:
                if s['score'] > breakout_score:
                    breakout_score = float(s['score'])
            elif s['setup_name'] == "RSI Exhaustion Reversal":
                reversal_score = float(s['score'])
                
        session_score = 20.0 if best_setup['setup_name'] in ["London Breakout", "NY Breakout"] else 0.0
        
        # We need to format the return dict to be compatible with existing code
        return {
            "final_direction": best_setup['direction'],
            "final_score": float(best_setup['score']),
            "setup_name": best_setup['setup_name'],
            "reason": best_setup['reason'],
            "all_setups": setups,
            "trend_score": float(trend_score),
            "breakout_score": float(breakout_score),
            "reversal_score": float(reversal_score),
            "session_score": float(session_score),
            "h4_trend": h4_trend
        }
