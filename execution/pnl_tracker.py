class PaperPnlTracker:
    def __init__(self):
        pass
        
    def calculate_execution_cost(self, signal: dict, slippage: float, latency_ms: float, fill_ratio: float) -> dict:
        """
        Calculates the execution cost and net expectancy in bps.
        """
        # Assume a base expected edge from the signal (e.g., 20 bps)
        base_edge_bps = signal['ml_prob'] * 40.0 # simple proxy for expected bps edge
        
        spread_cost_bps = signal.get('spread', 1.0)
        
        # Convert slippage points to bps (simplified approximation for tracking)
        slippage_cost_bps = slippage * 2.0 
        
        # Latency penalty: 0.1 bps per 10ms of latency above 50ms
        latency_penalty_bps = max(0, (latency_ms - 50) / 10.0) * 0.1
        
        total_cost_bps = spread_cost_bps + slippage_cost_bps + latency_penalty_bps
        
        # Adjust for partial fills: the edge is only captured on the filled portion, 
        # but costs (like latency penalty) might apply to the whole attempt.
        net_expectancy_bps = (base_edge_bps * fill_ratio) - total_cost_bps
        
        verdict = "SURVIVED"
        if net_expectancy_bps < 0:
            verdict = "REJECTED (NEGATIVE EV)"
        elif net_expectancy_bps < (base_edge_bps * 0.5):
            verdict = "DEGRADED"
            
        return {
            'base_edge_bps': base_edge_bps,
            'spread_cost_bps': spread_cost_bps,
            'slippage_cost_bps': slippage_cost_bps,
            'latency_penalty_bps': latency_penalty_bps,
            'net_expectancy_bps': net_expectancy_bps,
            'verdict': verdict
        }
