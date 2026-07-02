import numpy as np

class LatencyModel:
    def __init__(self, deterministic_ticks=2, random_seed=42):
        self.deterministic_ticks = deterministic_ticks
        self.rng = np.random.default_rng(random_seed)

    def simulate_latency_drift(self, entry_price: float, atr: float, direction: int) -> float:
        """
        Since we operate on M5 bars, we approximate the latency delay in terms of price drift.
        Deterministic delay: 1-3 ticks
        Stochastic delay: random jitter +- volatility (ATR)
        """
        # Assume 1 tick is roughly equivalent to a small fraction of ATR (e.g. 1% of ATR)
        tick_value = atr * 0.01 
        
        # Layer 1: Deterministic delay (always hurts us)
        deterministic_drift = self.deterministic_ticks * tick_value
        
        # Layer 2: Stochastic delay (random jitter)
        # Jitter can be positive or negative, scaled by volatility
        jitter = self.rng.normal(0, atr * 0.05)
        
        total_drift = deterministic_drift + jitter
        
        # Apply drift to entry price. 
        # If buying, drift usually increases price (worse entry). 
        # If selling, drift usually decreases price (worse entry).
        if direction == 1:
            actual_price = entry_price + abs(total_drift) # Force it to generally hurt, but jitter could help occasionally if negative enough
            # Actually, to be fair to jitter:
            actual_price = entry_price + deterministic_drift + jitter
        else:
            actual_price = entry_price - deterministic_drift + jitter
            
        return actual_price
