class PnLStabilizer:
    def __init__(self):
        self.high_water_mark = 0.0
        self.locked_profits = 0.0
        self.last_equity = 0.0
        
    def update_equity_state(self, current_equity: float, time_delta: float) -> dict:
        """
        Manages the Equity Curve via Ratcheting and Drawdown Velocity control.
        """
        state_updates = {'stability_score': 1.0, 'freeze': False}
        
        # 1. Profit Ratchet System
        if current_equity > self.high_water_mark:
            gains = current_equity - self.high_water_mark
            # Lock 40% of the new high water mark gains into low-risk allocation (cash out)
            self.locked_profits += gains * 0.40
            self.high_water_mark = current_equity
            
        # 2. Drawdown Velocity Monitor
        drawdown = self.high_water_mark - current_equity
        if drawdown > 0 and time_delta > 0:
            dd_speed = (self.last_equity - current_equity) / time_delta
            
            # If we are losing money too fast (velocity), not just the absolute loss
            if dd_speed > 1000.0: # Arbitrary high loss rate unit
                # Exponential decay of stability
                state_updates['stability_score'] = 0.1 
                
            elif dd_speed > 5000.0:
                # Capital Freeze: Rapid DD acceleration
                state_updates['freeze'] = True
                
        self.last_equity = current_equity
        return state_updates
