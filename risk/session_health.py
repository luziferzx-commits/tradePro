import collections
from enum import Enum
import logging

# Set up logging for session health changes
logger = logging.getLogger("SessionHealth")
logger.setLevel(logging.INFO)
# Avoid duplicating handlers if module is reloaded
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)


class HealthState(Enum):
    HEALTHY = 1
    WARNING = 2
    DEGRADED = 3
    DISABLED = 4


class CategoryHealthTracker:
    def __init__(self, name, category_type):
        self.name = name
        self.category_type = category_type
        
        self.trade_history = collections.deque(maxlen=30)
        self.state = HealthState.HEALTHY
        
        self.total_trades = 0
        self.consecutive_losses = 0
        self.current_drawdown_r = 0.0
        self.peak_pnl = 0.0
        self.current_pnl = 0.0
        
        # Hysteresis tracking
        self.disabled_until_trade_num = 0

    def evaluate_health(self, disabled_threshold: float = 0.75) -> HealthState:
        # If we haven't reached enough trades, assume healthy to let it build up
        if self.total_trades < 10:
            return HealthState.HEALTHY

        # Calculate metrics over the last 20 trades (or whatever we have up to 20)
        recent_20 = list(self.trade_history)[-20:]
        wins = sum(1 for p in recent_20 if p > 0)
        losses = len(recent_20) - wins
        
        gross_profit = sum(p for p in recent_20 if p > 0)
        gross_loss = abs(sum(p for p in recent_20 if p < 0))
        
        pf_20 = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # If currently DISABLED, check recovery conditions
        if self.state == HealthState.DISABLED:
            if self.total_trades >= self.disabled_until_trade_num and pf_20 > 1.2 and self.consecutive_losses < 3:
                logger.info(f"[{self.category_type}] {self.name} RECOVERED from DISABLED to HEALTHY (PF20: {pf_20:.2f})")
                self.state = HealthState.HEALTHY
            else:
                return HealthState.DISABLED

        # Determine new state based on thresholds
        # Only downgrade if we have enough trades (e.g., at least 10 in recent history)
        if len(recent_20) >= 10:
            new_state = self.state
            
            if pf_20 < disabled_threshold or self.consecutive_losses >= 7:
                new_state = HealthState.DISABLED
            elif pf_20 < 1.0 or self.consecutive_losses >= 5:
                new_state = HealthState.DEGRADED
            elif pf_20 < 1.3:
                new_state = HealthState.WARNING
            elif pf_20 >= 1.3 and self.current_drawdown_r < 5.0:
                new_state = HealthState.HEALTHY

            if new_state != self.state:
                if new_state == HealthState.DISABLED:
                    self.disabled_until_trade_num = self.total_trades + 10
                
                # Log state change
                logger.info(f"[{self.category_type}] {self.name} state changed: {self.state.name} -> {new_state.name} | PF20: {pf_20:.2f}, ConsecLoss: {self.consecutive_losses}, DD: {self.current_drawdown_r:.1f}R")
                self.state = new_state

        return self.state

    def update_result(self, pnl_r: float):
        """Update tracker with raw theoretical PnL (e.g., 1.5R or -1.0R)"""
        self.total_trades += 1
        self.trade_history.append(pnl_r)
        
        self.current_pnl += pnl_r
        if self.current_pnl > self.peak_pnl:
            self.peak_pnl = self.current_pnl
            self.current_drawdown_r = 0.0
        else:
            self.current_drawdown_r = self.peak_pnl - self.current_pnl

        if pnl_r < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0


class AdaptiveSessionHealth:
    def __init__(self):
        self.trackers = {}

    def _get_tracker(self, name: str, category_type: str) -> CategoryHealthTracker:
        key = f"{category_type}_{name}"
        if key not in self.trackers:
            self.trackers[key] = CategoryHealthTracker(name, category_type)
        return self.trackers[key]

    def get_risk_multiplier(self, features: dict, disabled_threshold: float = 0.75) -> float:
        """
        Evaluate health BEFORE applying the trade.
        Returns the risk multiplier (0.0 to 1.0) based on the most pessimistic state.
        """
        multipliers = []
        
        # We track multiple dimensions
        dimensions = {
            'symbol': features.get('symbol'),
            'session': features.get('session'),
            'market_regime': features.get('market_regime'),
            'direction': features.get('direction', 'SELL') # Default to SELL for Edge V2 if missing
        }
        
        session_regime = f"{features.get('session')} + {features.get('market_regime')}"
        dimensions['session_regime'] = session_regime

        for category_type, name in dimensions.items():
            if name:
                tracker = self._get_tracker(str(name), category_type)
                state = tracker.evaluate_health(disabled_threshold)
                
                mult = 1.0
                if state == HealthState.WARNING:
                    mult = 0.85
                elif state == HealthState.DEGRADED:
                    mult = 0.60
                elif state == HealthState.DISABLED:
                    if category_type in ['session_regime', 'session']:
                        mult = 0.0
                    else:
                        mult = 0.60 # Soft cap for non-session contexts
                
                # Apply rules: symbol and direction are diagnostic only
                if category_type not in ['symbol', 'direction']:
                    multipliers.append(mult)

        if not multipliers:
            return 1.0

        # Find the most pessimistic state (min multiplier)
        return min(multipliers)

    def update_trade(self, features: dict, pnl_r: float):
        """
        Update health AFTER the trade using raw/theoretical 1R PnL.
        """
        dimensions = {
            'symbol': features.get('symbol'),
            'session': features.get('session'),
            'market_regime': features.get('market_regime'),
            'direction': features.get('direction', 'SELL')
        }
        
        session_regime = f"{features.get('session')} + {features.get('market_regime')}"
        dimensions['session_regime'] = session_regime

        for category_type, name in dimensions.items():
            if name:
                tracker = self._get_tracker(str(name), category_type)
                tracker.update_result(pnl_r)

