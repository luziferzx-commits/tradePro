class AdversarialEV:
    def __init__(self):
        pass
        
    def calculate_net_ev(self, p_fill: float, p_preempt: float, expected_move: float, impact_cost: float, latency_cost: float) -> float:
        """
        Net EV = P(win_race) * P(fill) * ExpectedMove - ImpactCost - LatencyCost
        where P(win_race) = 1.0 - P(preempt)
        """
        p_win_race = 1.0 - p_preempt
        
        # If we are preempted, we might not get filled, or we get filled at a worse price.
        # For simplicity, we assume if preempted, EV is zero minus costs, or just scale the expected edge.
        # Actually, the requirement specifies:
        # EV = P(fill) * ExpectedMove - ImpactCost - LatencyCost
        # We will adjust P(fill) by P(win_race)
        
        adjusted_p_fill = p_fill * p_win_race
        
        ev = (adjusted_p_fill * expected_move) - impact_cost - latency_cost
        return ev
