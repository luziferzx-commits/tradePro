"""portfolio/portfolio_var.py"""
import numpy as np
import logging

logger = logging.getLogger(__name__)

class PortfolioVaR:
    @staticmethod
    def calculate_var(open_positions: list[dict], correlation_matrix: dict, confidence_level: float = 0.95, historical_returns: list[float] = None) -> dict:
        """
        Calculates VaR and CVaR. Returns a dict containing var, cvar, and the method used.
        """
        result = {"var": 0.0, "cvar": 0.0, "method": "", "warnings": []}
        
        if not open_positions:
            return result
            
        if historical_returns and len(historical_returns) > 30:
            # Historical VaR/CVaR
            returns_array = np.sort(historical_returns)
            # Ensure index is within bounds and captures the correct percentile (0-based)
            percentile_index = max(0, int(round((1.0 - confidence_level) * len(returns_array))) - 1)
            
            historical_var_pct = -returns_array[percentile_index] # VaR is a positive loss amount
            historical_cvar_pct = -np.mean(returns_array[:percentile_index+1])
            
            # Scale to current total risk
            total_risk = sum(pos.get('risk_amount', 0.0) for pos in open_positions)
            
            # Simple assumption: historic returns are relative to typical risk.
            result["var"] = max(0.0, float(historical_var_pct * total_risk))
            result["cvar"] = max(0.0, float(historical_cvar_pct * total_risk))
            result["method"] = "HISTORICAL"
        else:
            # Parametric Fallback
            result["warnings"].append("PARAMETRIC_FALLBACK_USED")
            logger.warning("PARAMETRIC_FALLBACK_USED: Calculating VaR via covariance matrix without sufficient historical data.")
            
            n = len(open_positions)
            risks = np.array([pos.get('risk_amount', 0.0) for pos in open_positions])
            
            corr_mat = np.eye(n)
            for i in range(n):
                for j in range(n):
                    if i != j:
                        sym1 = open_positions[i].get('symbol', '')
                        sym2 = open_positions[j].get('symbol', '')
                        key1 = f"{sym1}_{sym2}"
                        key2 = f"{sym2}_{sym1}"
                        c = correlation_matrix.get(key1, correlation_matrix.get(key2, 0.0))
                        
                        side1 = open_positions[i].get('side')
                        side2 = open_positions[j].get('side')
                        if side1 != side2:
                            c = -c
                            
                        corr_mat[i, j] = c
                        
            port_variance = risks.T @ corr_mat @ risks
            port_volatility = np.sqrt(max(0.0, port_variance))
            
            z_score = 1.645 if confidence_level == 0.95 else 2.33
            
            var = port_volatility * z_score
            cvar = var * 1.25 # Rule of thumb approximation for normal distribution tail
            
            result["var"] = float(var)
            result["cvar"] = float(cvar)
            result["method"] = "PARAMETRIC"
            
        return result
