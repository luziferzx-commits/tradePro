class SurvivorAllocator:
    def __init__(self, target_volatility=0.10):
        self.target_volatility = target_volatility
        
    def calculate_base_allocation(self, equity: float, win_rate: float, win_loss_ratio: float, 
                                  stability_score: float, regime_multiplier: float, capacity_decay: float) -> float:
        """
        Calculates Institutional Position Sizing based on the Half-Kelly Hybrid Model.
        Survivor alpha is low frequency and requires under-leveraging by design.
        """
        # 1. Calculate Full Kelly
        # K = W - ((1 - W) / R)
        if win_loss_ratio <= 0:
            return 0.0
            
        kelly_fraction = win_rate - ((1.0 - win_rate) / win_loss_ratio)
        
        if kelly_fraction <= 0:
            return 0.0
            
        # 2. Apply Half-Kelly (Standard institutional dampening)
        half_kelly = kelly_fraction * 0.5
        
        # 3. Hybrid Institutional Equation
        position_size = (
            equity *
            self.target_volatility *
            half_kelly *
            stability_score *
            regime_multiplier *
            capacity_decay
        )
        
        return position_size
