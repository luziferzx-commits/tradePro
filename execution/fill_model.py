import random

class FillModel:
    def __init__(self):
        pass
        
    def simulate_fill(self, signal: dict) -> dict:
        """
        Calculates Fill Probability and Partial Fill behavior based on regime and volatility.
        """
        regime = signal['regime']
        volatility = signal.get('volatility_factor', 1.0)
        signal_strength = signal['ml_prob'] * signal['market_score']
        
        # Base fill probability
        fill_prob = 0.95
        
        if regime == "RANGING":
            fill_prob -= 0.15 # Lower consistency
        elif regime == "TRENDING":
            fill_prob += 0.04 # Better consistency
            
        if volatility > 1.5:
            fill_prob -= 0.20 # High vol reduces fill probability
            
        # Is it a partial fill?
        is_partial = random.random() > fill_prob
        
        fill_ratio = 1.0
        policy = "PASSIVE_WAIT"
        
        if is_partial:
            fill_ratio = random.uniform(0.1, 0.8) # Partially filled between 10% and 80%
            
            # Determine policy based on CIO rules
            if volatility > 1.5 or signal['spread'] > 2.0:
                policy = "CANCEL_REMAINDER"
            elif signal_strength > 0.60 and regime == "TRENDING":
                policy = "CONTROLLED_CHASE"
            else:
                policy = "PASSIVE_WAIT"
                
        return {
            'fill_ratio': fill_ratio,
            'is_partial': is_partial,
            'policy': policy
        }
