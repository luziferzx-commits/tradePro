import math

class AdversarialEmulator:
    def __init__(self, my_latency_rank=2):
        """
        Rank 1: Tier-1 HFT (Colocated FPGA)
        Rank 2: Tier-2 HFT (Us, standard colocation)
        Rank 3: Institutional
        Rank 4: Retail
        """
        self.my_latency_rank = my_latency_rank
        
    def calculate_preemption_prob(self, signal_visibility: float, volatility: float) -> float:
        """
        Calculates the probability that a competitor with a better latency rank 
        acts on the same signal before us.
        signal_visibility [0, 1]: How obvious the signal is (e.g. 0.9 for massive vacuum)
        volatility: scales the race intensity
        """
        # If we are Rank 1, no one preempts us (ignoring equal ties for simplicity)
        if self.my_latency_rank <= 1:
            return 0.0
            
        # The worse our rank, the higher the chance of preemption
        rank_penalty = (self.my_latency_rank - 1) * 0.3
        
        p_preempt = signal_visibility * rank_penalty * (1.0 + volatility)
        
        # Cap at 99% (always a small chance they miss it)
        return min(p_preempt, 0.99)
