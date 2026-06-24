class L2ImpactModel:
    def __init__(self, k_factor=0.05, alpha=0.6):
        self.k_factor = k_factor
        self.alpha = alpha
        
    def simulate_impact(self, order_size: float, liquidity_depth: float, volatility_multiplier: float = 1.0) -> float:
        """
        Simulates the non-linear price impact of an aggressive market order against L2 depth.
        Using Square-Root / Fractional Power Law: Impact ~ (Q / V_D)^0.6
        """
        if liquidity_depth <= 0:
            return float('inf') # Infinite impact on empty book
            
        base_impact = self.k_factor * ((order_size / liquidity_depth) ** self.alpha)
        
        # Apply regime multiplier (e.g. spread explosion in high vol)
        total_impact = base_impact * volatility_multiplier
        
        return total_impact
