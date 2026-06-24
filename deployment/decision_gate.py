class DecisionGate:
    @staticmethod
    def evaluate_deployment(prob_ruin: float, expectancy: float, max_dd: float, 
                            survival_trades: int, stability_score: float) -> dict:
        """
        The Institutional Hard Gate.
        ANY violation = REJECT.
        """
        reasons = []
        
        if prob_ruin >= 0.01:
            reasons.append(f"Risk of Ruin too high: {prob_ruin*100:.2f}% (Limit: < 1.0%)")
            
        if expectancy <= 0:
            reasons.append(f"Negative Expectancy after execution realism: {expectancy:.4f} bps (Limit: > 0)")
            
        if max_dd >= 0.25:
            reasons.append(f"Max Drawdown too deep: {max_dd*100:.2f}% (Limit: < 25.0%)")
            
        if survival_trades <= 1000:
            reasons.append(f"Insufficient survival trades: {survival_trades} (Limit: > 1000)")
            
        if stability_score <= 0.7:
            reasons.append(f"System Stability Score too low: {stability_score:.2f} (Limit: > 0.7)")
            
        if not reasons:
            return {
                'decision': 'DEPLOY',
                'reasons': ['All Institutional Criteria Passed']
            }
        else:
            return {
                'decision': 'REJECT',
                'reasons': reasons
            }
