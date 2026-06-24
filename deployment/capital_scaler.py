class CapitalScaler:
    def __init__(self, target_volatility_annual=0.15, max_kelly=0.25):
        self.target_volatility = target_volatility_annual
        self.max_kelly = max_kelly

    def calculate_drawdown_adjustment(self, current_drawdown: float) -> float:
        """
        Drawdown brakes:
        if DD > 10% -> reduce size by 50%
        if DD > 20% -> reduce size by 80%
        """
        if current_drawdown > 0.20:
            return 0.20
        elif current_drawdown > 0.10:
            return 0.50
        else:
            return 1.0

    def calculate_position_size(self, current_equity: float, current_drawdown: float, 
                                stability_score: float, expected_win_rate: float, 
                                expected_rr_ratio: float, strategy_volatility_annual: float) -> float:
        """
        Calculates absolute dollar allocation size.
        Size = Equity * VolTargeting * StabilityScore * DrawdownAdjustment * KellyFraction
        """
        if strategy_volatility_annual <= 0:
            return 0.0
            
        # 1. Volatility Targeting (Fraction of capital to allocate to hit portfolio target)
        vol_targeting = self.target_volatility / strategy_volatility_annual
        
        # 2. Kelly Fraction
        if expected_rr_ratio <= 0:
            kelly = 0.0
        else:
            kelly = expected_win_rate - ((1.0 - expected_win_rate) / expected_rr_ratio)
            
        kelly_capped = min(max(kelly, 0.0), self.max_kelly)
        
        # 3. Drawdown Adjustment
        dd_adj = self.calculate_drawdown_adjustment(current_drawdown)
        
        # Final Weight Fraction
        allocation_fraction = vol_targeting * stability_score * dd_adj * kelly_capped
        
        # Cap absolute leverage if necessary (e.g. max 2.0x equity)
        allocation_fraction = min(allocation_fraction, 2.0)
        
        return current_equity * allocation_fraction
