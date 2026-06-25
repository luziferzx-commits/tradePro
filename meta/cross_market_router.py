class CrossMarketRouter:
    def __init__(self, lambda_corr=0.1, mu_instability=0.2):
        self.lambda_corr = lambda_corr
        self.mu_instability = mu_instability
        
    def allocate_capital(self, desks: dict, total_capital: float, global_correlation_risk: float) -> dict:
        """
        Capital Arbitration Engine.
        Capital goes where marginal efficiency is highest, not where returns are highest.
        """
        allocations = {}
        scores = {}
        total_score = 0.0
        
        for desk_id, metrics in desks.items():
            # max Σ (RAROC_i × RegimeFit_i × MarginalCapacity_i) − λ × CorrelationRisk − μ × CapitalInstability
            
            raroc = metrics.get('raroc', 0.0)
            regime_fit = metrics.get('regime_fit', 0.0)
            marginal_capacity = metrics.get('marginal_capacity', 1.0)
            capital_instability = metrics.get('capital_instability', 0.0)
            
            score = (raroc * regime_fit * marginal_capacity) - (self.lambda_corr * global_correlation_risk) - (self.mu_instability * capital_instability)
            
            if score > 0:
                scores[desk_id] = score
                total_score += score
            else:
                scores[desk_id] = 0.0
                
        # Proportional allocation based on score
        for desk_id in desks.keys():
            if total_score > 0:
                allocations[desk_id] = (scores[desk_id] / total_score) * total_capital
            else:
                allocations[desk_id] = 0.0
                
        return allocations
