import pandas as pd
import os
from typing import List
from .base import SignalDecision
from .registry import StrategyRegistry

class EnsembleRouter:
    """
    Evaluates independent strategies and ranks them by Expected Value (EV).
    Returns the single best SignalDecision or a NEUTRAL signal if none meet the edge criteria.
    """
    
    def __init__(self, trading_cost_r: float = 0.1, min_ev_threshold: float = 0.05):
        self.trading_cost_r = trading_cost_r
        self.min_ev_threshold = min_ev_threshold

    def route(self, df: pd.DataFrame, regime: dict, registry: StrategyRegistry, ml_predictions: dict = None, session_info: dict = None) -> SignalDecision:
        if df.empty:
            return self._neutral("Empty DataFrame")
            
        candidates: List[SignalDecision] = []
        is_session_aware = os.getenv("SESSION_AWARE_ROUTER") == "true"
        
        session_label = session_info.get("session_label", "UNKNOWN") if session_info else "UNKNOWN"
        is_overlap = session_info.get("is_overlap_session", False) if session_info else False
        
        # 1. Gather all candidate signals
        for strategy in registry.get_all_strategies():
            signal = strategy.generate_signal(df, regime)
            
            # Inject session info
            if session_info:
                signal.session_label = session_label
                signal.minutes_from_session_open = session_info.get("minutes_from_session_open", 0)
                signal.is_overlap_session = is_overlap

            if signal.direction != "NEUTRAL" and not strategy.is_disabled_by_evidence:
                # Apply Session-Aware Rules
                if is_session_aware:
                    strategy_name = strategy.__class__.__name__
                    if session_label == "OFF_SESSION":
                        signal.status = "REJECTED"
                        signal.rejection_reason = "OFF_SESSION disabled"
                        signal.direction = "NEUTRAL"
                    elif session_label == "ASIA":
                        # ASIA: prefer range/reversion, block weak breakout
                        if strategy_name == "StrategyABreakout" and regime.get("volatility") != "EXPANDING":
                            signal.status = "REJECTED"
                            signal.rejection_reason = "Breakout blocked in ASIA"
                            signal.direction = "NEUTRAL"
                    elif session_label == "LONDON":
                        # LONDON: allow breakout + trend (no rejections needed, natural EV will sort it)
                        pass
                    elif session_label == "NEW_YORK":
                        # NEW_YORK: allow trend + volatility expansion
                        # block mean reversion if trend is strong
                        if strategy_name == "StrategyCMeanReversion" and regime.get("trend") in ["STRONG_UP", "STRONG_DOWN"]:
                            signal.status = "REJECTED"
                            signal.rejection_reason = "Mean Reversion blocked in NY Strong Trend"
                            signal.direction = "NEUTRAL"
                    elif session_label == "LONDON_NY_OVERLAP":
                        # OVERLAP: stricter filter, high EV only
                        pass
                
                if signal.direction != "NEUTRAL":
                    candidates.append(signal)
                
        if not candidates:
            return self._neutral("No strategies generated active signals")
            
        # 2. Calculate EV and filter
        valid_candidates = []
        for sig in candidates:
            # TODO: Inject real historical Win Rate from backtest DB or ML Predictor
            # For now, we estimate based on ML prediction if available, else standard baseline
            win_prob = 0.40 
            if ml_predictions and 'probability' in ml_predictions:
                win_prob = ml_predictions['probability']
                
            loss_prob = 1.0 - win_prob
            
            # EV = (Win% * Reward) - (Loss% * Risk) - Cost
            # Assuming risk_r is always 1.0 standard R unit
            expected_value_after_cost = (win_prob * sig.expected_rr) - (loss_prob * 1.0) - self.trading_cost_r
            
            # Apply session-specific EV penalties if any were marked earlier (e.g. overlap)
            if sig.session_label == "LONDON_NY_OVERLAP":
                expected_value_after_cost -= 0.05
            
            sig.edge_score = expected_value_after_cost
            sig.cost_estimate = self.trading_cost_r
            
            if expected_value_after_cost > self.min_ev_threshold:
                sig.status = "APPROVED"
                valid_candidates.append(sig)
            else:
                sig.status = "REJECTED"
                sig.rejection_reason = f"Negative or low EV: {expected_value_after_cost:.2f}"
                
        if not valid_candidates:
            return self._neutral("All candidates rejected due to low Expected Value")
            
        # 3. Anti-overlap / Select Best
        # Rank by EV (highest first)
        valid_candidates.sort(key=lambda x: x.edge_score, reverse=True)
        
        best_signal = valid_candidates[0]
        return best_signal

    def _neutral(self, reason: str) -> SignalDecision:
        return SignalDecision(
            strategy_id="EnsembleRouter",
            setup_name="None",
            direction="NEUTRAL",
            confidence_score=0.0,
            entry_reason=reason,
            stop_loss=0.0,
            take_profit=0.0,
            expected_rr=0.0,
            invalidation_reason=reason,
            required_regime="ANY"
        )
