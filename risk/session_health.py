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
    def __init__(self, name, category_type, rolling_window=20, recovery_trades=10):
        self.name = name
        self.category_type = category_type
        self.rolling_window = rolling_window
        self.recovery_trades = recovery_trades
        
        # Keep slightly more history than needed just in case
        self.trade_history = collections.deque(maxlen=self.rolling_window + 10)
        self.state = HealthState.HEALTHY
        
        self.total_trades = 0
        self.consecutive_losses = 0
        self.current_drawdown_r = 0.0
        self.peak_pnl = 0.0
        self.current_pnl = 0.0
        
        # Hysteresis tracking
        self.disabled_until_trade_num = 0

    def evaluate_health(self, disabled_threshold: float = 0.70) -> HealthState:
        # If we haven't reached enough trades, assume healthy to let it build up
        if self.total_trades < min(10, self.rolling_window // 2):
            return HealthState.HEALTHY

        # Calculate metrics over the last N trades
        recent_n = list(self.trade_history)[-self.rolling_window:]
        wins = sum(1 for p in recent_n if p > 0)
        losses = len(recent_n) - wins
        
        gross_profit = sum(p for p in recent_n if p > 0)
        gross_loss = abs(sum(p for p in recent_n if p < 0))
        
        pf_n = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # If currently DISABLED, check recovery conditions
        if self.state == HealthState.DISABLED:
            if self.total_trades >= self.disabled_until_trade_num and pf_n > 1.2 and self.consecutive_losses < 3:
                logger.info(f"[{self.category_type}] {self.name} RECOVERED from DISABLED to HEALTHY (PF{self.rolling_window}: {pf_n:.2f})")
                self.state = HealthState.HEALTHY
            else:
                return HealthState.DISABLED

        # Determine new state based on thresholds
        if len(recent_n) >= min(10, self.rolling_window // 2):
            new_state = self.state
            
            if pf_n < disabled_threshold or self.consecutive_losses >= 7:
                new_state = HealthState.DISABLED
            elif pf_n < 1.0 or self.consecutive_losses >= 5:
                new_state = HealthState.DEGRADED
            elif pf_n < 1.3:
                new_state = HealthState.WARNING
            elif pf_n >= 1.3 and self.current_drawdown_r < 5.0:
                new_state = HealthState.HEALTHY

            if new_state != self.state:
                if new_state == HealthState.DISABLED:
                    self.disabled_until_trade_num = self.total_trades + self.recovery_trades
                
                # Log state change
                logger.info(f"[{self.category_type}] {self.name} state changed: {self.state.name} -> {new_state.name} | PF{self.rolling_window}: {pf_n:.2f}, ConsecLoss: {self.consecutive_losses}, DD: {self.current_drawdown_r:.1f}R")
                self.state = new_state

        return self.state

    def update_result(self, pnl_r: float):
        """Update tracker with raw theoretical PnL"""
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
    def __init__(self, rolling_window=20, recovery_trades=10, 
                 disabled_threshold=0.70, degraded_multiplier=0.60, warning_multiplier=0.85):
        self.trackers = {}
        self.rolling_window = rolling_window
        self.recovery_trades = recovery_trades
        self.disabled_threshold = disabled_threshold
        self.degraded_multiplier = degraded_multiplier
        self.warning_multiplier = warning_multiplier

    def _get_tracker(self, name: str, category_type: str) -> CategoryHealthTracker:
        key = f"{category_type}_{name}"
        if key not in self.trackers:
            self.trackers[key] = CategoryHealthTracker(
                name, category_type, 
                rolling_window=self.rolling_window, 
                recovery_trades=self.recovery_trades
            )
        return self.trackers[key]

    def get_risk_multiplier(self, features: dict) -> float:
        """
        Evaluate health BEFORE applying the trade.
        Returns the risk multiplier based on the most pessimistic state.
        """
        multipliers = []
        
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
                state = tracker.evaluate_health(self.disabled_threshold)
                
                mult = 1.0
                if state == HealthState.WARNING:
                    mult = self.warning_multiplier
                elif state == HealthState.DEGRADED:
                    mult = self.degraded_multiplier
                elif state == HealthState.DISABLED:
                    if category_type in ['session_regime', 'session']:
                        mult = 0.0
                    else:
                        mult = self.degraded_multiplier # Soft cap for non-session contexts
                
                # Apply rules: symbol and direction are diagnostic only
                if category_type not in ['symbol', 'direction']:
                    multipliers.append(mult)

        if not multipliers:
            return 1.0

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
