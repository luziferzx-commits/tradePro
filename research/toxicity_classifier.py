class ToxicityClassifier:
    def __init__(self):
        pass
        
    def calculate_lpr(self, initial_depth: float, depth_after_dt: float) -> float:
        """
        Liquidity Persistence Ratio (LPR)
        """
        if initial_depth <= 0:
            return 0.0
        return depth_after_dt / initial_depth
        
    def classify_flow(self, obi: float, lpr: float, price_follow_through: bool) -> str:
        """
        Differentiates between Informed Flow (real intent) and Toxic Flow (spoofing).
        """
        # If there is high imbalance but the liquidity vanishes quickly without price moving
        if abs(obi) > 0.7 and lpr < 0.2 and not price_follow_through:
            return 'TOXIC_SPOOF'
            
        # If there is persistent imbalance and price actually moves with it
        if abs(obi) > 0.5 and lpr > 0.6 and price_follow_through:
            return 'INFORMED_ACCUMULATION'
            
        return 'NOISE'
