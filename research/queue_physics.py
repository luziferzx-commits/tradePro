import math

class QueuePhysics:
    def __init__(self):
        pass
        
    def estimate_fill_probability(self, queue_depth: float, incoming_aggressive_flow: float, liquidity_decay_factor: float) -> float:
        """
        Estimates the probability that our limit order gets filled, given we are at `queue_depth`
        and there is a certain amount of `incoming_aggressive_flow` eating into that queue.
        """
        if incoming_aggressive_flow <= 0:
            return 0.0
            
        # P(fill) = exp(-QueueDepth / IncomingAggressiveFlow) * LiquidityDecayFactor
        exponent = - (queue_depth / incoming_aggressive_flow)
        p_fill = math.exp(exponent) * liquidity_decay_factor
        
        return min(max(p_fill, 0.0), 1.0)
