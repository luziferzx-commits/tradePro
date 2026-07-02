import numpy as np

class LiquidityImpactModel:
    def __init__(self, max_participation_rate=0.05, impact_coefficient=0.1):
        self.max_participation_rate = max_participation_rate
        self.impact_coefficient = impact_coefficient

    def check_capacity(self, order_size: float, avg_volume: float) -> float:
        """
        MaxOrderSize <= 5% of Average Tick Volume
        Returns the accepted order size. If order_size > max, it caps it.
        """
        max_size = avg_volume * self.max_participation_rate
        return min(order_size, max_size)

    def calculate_market_impact(self, order_size: float, market_volume: float) -> float:
        """
        Impact = sqrt(OrderSize / MarketVolume)
        Returns the price impact percentage.
        """
        if market_volume <= 0 or order_size <= 0:
            return 0.0
            
        # Institutional square-root model
        ratio = order_size / market_volume
        impact = self.impact_coefficient * np.sqrt(ratio)
        return impact
