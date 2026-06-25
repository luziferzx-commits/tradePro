class PassiveEMS:
    def __init__(self):
        self.mode = 'PASSIVE' # Default mode
        
    def set_mode(self, regime_shift_confirmed: bool):
        if regime_shift_confirmed:
            self.mode = 'REACTIVE'
        else:
            self.mode = 'PASSIVE'
            
    def route_order(self, alpha_signal: dict) -> dict:
        """
        Routes the Survivor Alpha.
        Passive mode fundamentally changes the EV math by avoiding the Square-Root impact cost.
        Instead, we capture the spread, but we take on queue risk.
        """
        if self.mode == 'PASSIVE':
            return {
                'execution_type': 'LIMIT_MAKER',
                'impact_cost_expected': 0.0, # We provide liquidity, no market impact
                'spread_capture': True,      # We earn the spread instead of paying it
                'fill_urgency': 'LOW'
            }
        else:
            return {
                'execution_type': 'MARKET_TAKER',
                'impact_cost_expected': 'SQUARE_ROOT_LAW',
                'spread_capture': False,
                'fill_urgency': 'HIGH'
            }
