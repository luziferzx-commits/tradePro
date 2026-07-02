import numpy as np

class FillSimulator:
    def __init__(self, random_seed=42):
        self.rng = np.random.default_rng(random_seed)

    def simulate_fill(self, order_size: float, liquidity_depth: float) -> dict:
        """
        P(fill) = exp(-OrderSize / LiquidityDepth)
        FilledSize = OrderSize * LiquidityRatio * RandomShock
        """
        if liquidity_depth <= 0 or order_size <= 0:
            return {'status': 'REJECTED', 'filled_size': 0.0}
            
        # Probability of a full fill
        p_fill = np.exp(-order_size / liquidity_depth)
        
        # Determine outcome
        rand_val = self.rng.random()
        
        if rand_val <= p_fill:
            # Full Fill
            return {'status': 'FULL_FILL', 'filled_size': order_size}
        else:
            # Partial fill or missed trade
            # Missed trade occurs if the random shock is severe
            random_shock = self.rng.uniform(0.1, 0.9)
            liquidity_ratio = liquidity_depth / (order_size + liquidity_depth)
            
            filled_size = order_size * liquidity_ratio * random_shock
            
            # If filled size is too small (e.g. < 5% of order), treat as missed
            if filled_size < (order_size * 0.05):
                return {'status': 'MISSED', 'filled_size': 0.0}
                
            return {'status': 'PARTIAL_FILL', 'filled_size': filled_size}
