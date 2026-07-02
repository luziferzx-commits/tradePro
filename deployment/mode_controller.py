class ModeController:
    @staticmethod
    def evaluate_mode(current_drawdown: float, regime: str) -> str:
        """
        Adaptive Regime Switching (System Driven)
        
        Preservation Mode:
        - Trigger: DD > 10% or Vol Spike
        - Behavior: Reduce size, trade only highest S-score alphas
        
        Growth Mode:
        - Trigger: DD < 5% and Stable Regime
        - Behavior: Full alpha basket, higher risk parity
        """
        if current_drawdown > 0.10 or regime == 'HIGH_VOL_EXPANSION':
            return 'PRESERVATION'
            
        if current_drawdown < 0.05 and regime in ['NORMAL_VOLATILITY', 'LOW_VOL_COMPRESSION']:
            return 'GROWTH'
            
        # Default to neutral/current transition
        return 'NEUTRAL'
