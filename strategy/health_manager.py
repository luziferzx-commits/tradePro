import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class StrategyHealthState:
    strategy_id: str
    health_score: float = 100.0
    status: str = "INSUFFICIENT_SAMPLE"
    risk_multiplier: float = 0.25
    rolling_pf: float = 0.0
    rolling_expectancy_r: float = 0.0
    rolling_win_rate: float = 0.0
    rolling_max_dd: float = 0.0
    average_rr: float = 0.0
    trade_count: int = 0
    updated_at: str = ""

class StrategyHealthManager:
    """
    Adaptive Intelligence Layer: Strategy Health Manager
    Calculates health score (0-100) and risk multiplier based on rolling metrics.
    """
    
    def __init__(self, state_file: str = "config/strategy_health_state.json"):
        self.state_file = state_file
        self.states: Dict[str, StrategyHealthState] = {}
        self.load_state()

    def load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    for strat_id, strat_data in data.items():
                        self.states[strat_id] = StrategyHealthState(**strat_data)
            except Exception as e:
                logger.error(f"Failed to load strategy health state: {e}")
                
    def save_state(self):
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        try:
            with open(self.state_file, 'w') as f:
                data = {k: asdict(v) for k, v in self.states.items()}
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save strategy health state: {e}")

    def get_state(self, strategy_id: str) -> StrategyHealthState:
        if strategy_id not in self.states:
            self.states[strategy_id] = StrategyHealthState(strategy_id=strategy_id, updated_at=datetime.now().isoformat())
        return self.states[strategy_id]

    def _calculate_score(self, state: StrategyHealthState) -> float:
        score = 0.0
        
        # 1. Profit Factor (35%)
        # > 1.5 = 35, 1.15-1.5 = 20-35, 1.0-1.15 = 10-20, < 1.0 = 0
        if state.rolling_pf >= 1.5:
            score += 35
        elif state.rolling_pf >= 1.15:
            score += 20 + 15 * ((state.rolling_pf - 1.15) / (1.5 - 1.15))
        elif state.rolling_pf >= 1.0:
            score += 10 + 10 * ((state.rolling_pf - 1.0) / (1.15 - 1.0))
        
        # 2. Expectancy R (30%)
        # > 0.2R = 30, > 0.05R = 15, <= 0 = 0
        if state.rolling_expectancy_r >= 0.2:
            score += 30
        elif state.rolling_expectancy_r > 0:
            score += 15 * (state.rolling_expectancy_r / 0.2)
            
        # 3. Drawdown Control (20%)
        # 0% DD = 20, 5% DD = 10, > 10% DD = 0
        if state.rolling_max_dd <= 0.02:
            score += 20
        elif state.rolling_max_dd <= 0.05:
            score += 10 + 10 * (1 - (state.rolling_max_dd - 0.02)/0.03)
        elif state.rolling_max_dd <= 0.10:
            score += 10 * (1 - (state.rolling_max_dd - 0.05)/0.05)
            
        # 4. Win Rate / RR Synergy (10%)
        # Simple measure: if WinRate * AverageRR > 0.5 (e.g. 33% wr and 1.5 rr)
        synergy = state.rolling_win_rate * state.average_rr
        if synergy >= 0.6:
            score += 10
        elif synergy > 0:
            score += 10 * (synergy / 0.6)
            
        # 5. Sample Size Confidence (5%)
        # 100+ trades = 5 points
        if state.trade_count >= 100:
            score += 5
        else:
            score += 5 * (state.trade_count / 100.0)
            
        return min(max(score, 0.0), 100.0)

    def _apply_thresholds(self, state: StrategyHealthState):
        if state.trade_count < 30:
            state.status = "INSUFFICIENT_SAMPLE"
            state.risk_multiplier = 0.25
            return

        if state.health_score >= 70:
            state.status = "HEALTHY"
            state.risk_multiplier = 1.0
        elif state.health_score >= 50:
            state.status = "DEGRADED"
            state.risk_multiplier = 0.50
        elif state.health_score >= 40:
            state.status = "WATCHLIST"
            state.risk_multiplier = 0.25
        else:
            state.status = "DISABLED_BY_EVIDENCE"
            state.risk_multiplier = 0.0

    def update_metrics(self, strategy_id: str, pf: float, expectancy: float, win_rate: float, max_dd: float, avg_rr: float, trade_count: int):
        """Update metrics and recalculate health. Used by both backtest/shadow memory loop and DB nightly rebuild."""
        state = self.get_state(strategy_id)
        
        state.rolling_pf = pf
        state.rolling_expectancy_r = expectancy
        state.rolling_win_rate = win_rate
        state.rolling_max_dd = max_dd
        state.average_rr = avg_rr
        state.trade_count = trade_count
        state.updated_at = datetime.now().isoformat()
        
        state.health_score = self._calculate_score(state)
        self._apply_thresholds(state)
        
        # Don't persist on every memory update to save IO, rely on manual save_state()
