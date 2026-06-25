import numpy as np
import pandas as pd

class RiskOfRuinSimulator:
    def __init__(self, initial_equity=500.0, ruin_threshold=0.5, num_paths=10000, num_trades=1000, random_seed=42):
        self.initial_equity = initial_equity
        self.ruin_equity = initial_equity * ruin_threshold
        self.num_paths = num_paths
        self.num_trades = num_trades
        self.rng = np.random.default_rng(random_seed)

    def simulate(self, win_rate: float, avg_win_pct: float, avg_loss_pct: float, 
                 stdev_pct: float) -> dict:
        """
        Layer 1: Simulate trade paths
        Layer 2: Track drawdown
        Layer 3: Terminal Ruin Condition
        """
        # If expectancy is severely negative, P(ruin) will be ~1.0
        # If win_rate is 0, we automatically fail.
        if win_rate <= 0:
            return {
                'prob_ruin': 1.0,
                'avg_max_dd': 1.0,
                'avg_terminal_equity': 0.0
            }

        ruin_count = 0
        total_max_dd = 0.0
        total_terminal = 0.0

        for path in range(self.num_paths):
            equity = self.initial_equity
            max_equity = self.initial_equity
            max_dd = 0.0
            ruined = False
            
            # Generate a sequence of trades
            # 1 = Win, 0 = Loss
            outcomes = self.rng.binomial(1, win_rate, self.num_trades)
            
            # Generate normally distributed returns centered around avg_win and avg_loss
            win_returns = self.rng.normal(avg_win_pct, stdev_pct, self.num_trades)
            loss_returns = self.rng.normal(avg_loss_pct, stdev_pct, self.num_trades)
            
            for i in range(self.num_trades):
                if outcomes[i] == 1:
                    ret = max(0.0001, win_returns[i]) # Force win to be positive
                else:
                    ret = min(-0.0001, loss_returns[i]) # Force loss to be negative
                    
                # Standard risk per trade roughly 1-2%, let's assume the ret is the % equity change 
                # (For simplicity in this generic MC without dynamic sizing)
                # Actually, Capital Scaler does sizing, but Risk of Ruin MC usually assumes fixed fractional
                # to test the baseline statistical survival.
                # Let's assume the ret represents the base return on capital deployed.
                # If we deploy 10% of equity, equity change = equity * 0.10 * ret
                # Let's assume ret is already normalized to portfolio equity impact.
                
                equity += equity * ret
                
                if equity > max_equity:
                    max_equity = equity
                    
                dd = (max_equity - equity) / max_equity
                if dd > max_dd:
                    max_dd = dd
                    
                if equity <= self.ruin_equity:
                    ruined = True
                    break
                    
            if ruined:
                ruin_count += 1
            total_max_dd += max_dd
            total_terminal += equity
            
        prob_ruin = ruin_count / self.num_paths
        avg_max_dd = total_max_dd / self.num_paths
        avg_terminal = total_terminal / self.num_paths
        
        return {
            'prob_ruin': prob_ruin,
            'avg_max_dd': avg_max_dd,
            'avg_terminal_equity': avg_terminal
        }
