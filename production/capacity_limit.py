import math

class CapacityLimitEngine:
    def __init__(self, participation_cap=0.05, toxicity_decay_threshold=0.8):
        self.participation_cap = participation_cap
        self.toxicity_decay_threshold = toxicity_decay_threshold
        
    def calculate_max_aum(self, market_liquidity_usd: float) -> float:
        """
        Calculates the absolute maximum capital capacity for the Survivor Alpha.
        MaxAUM ∝ sqrt(market_liquidity)
        If you scale Survivor Alpha too much, you become the toxicity.
        """
        # Baseline scaling factor
        scaling_constant = 1000.0 
        
        # The edge decays as a function of our participation rate
        capacity_limit = (
            math.sqrt(market_liquidity_usd) * 
            scaling_constant * 
            self.toxicity_decay_threshold * 
            self.participation_cap
        )
        
        return capacity_limit
        
    def get_capacity_decay_factor(self, proposed_allocation_usd: float, max_aum_usd: float) -> float:
        """
        Returns a scaling factor [0, 1] to taper allocation as we approach the strategy's capacity limit.
        """
        if max_aum_usd <= 0:
            return 0.0
            
        utilization = proposed_allocation_usd / max_aum_usd
        
        if utilization < 0.5:
            return 1.0 # Fully efficient
        elif utilization >= 1.0:
            return 0.0 # Full capacity reached, cannot allocate more without destroying edge
        else:
            # Linear decay from 50% to 100% utilization
            return 1.0 - ((utilization - 0.5) * 2.0)
