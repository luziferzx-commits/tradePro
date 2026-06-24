from typing import Dict, Any

class AlphaHealthScore:
    """
    Computes a 0-100 Health Score for an Alpha.
    Used by the Router to scale capital allocations dynamically.
    """
    @staticmethod
    def calculate(metrics: Dict[str, float]) -> float:
        """
        metrics dict expects:
        - rolling_sharpe: float
        - max_drawdown: float (positive number representing percentage, e.g., 0.10 for 10%)
        - pbo: float (0 to 1)
        - stability: float (0 to 1)
        - feature_drift: float (0 to 1, where 1 is severe drift)
        - execution_slippage_bps: float
        """
        score = 100.0
        
        # 1. Rolling Sharpe (Base)
        sharpe = metrics.get('rolling_sharpe', 0.0)
        if sharpe < 0:
            score -= 40
        elif sharpe < 1.0:
            score -= 20
            
        # 2. Drawdown penalty
        dd = metrics.get('max_drawdown', 0.0)
        if dd > 0.15:
            score -= 30
        elif dd > 0.05:
            score -= 10
            
        # 3. PBO penalty
        pbo = metrics.get('pbo', 0.0)
        if pbo > 0.5:
            score -= 50
        elif pbo > 0.2:
            score -= 20
            
        # 4. Feature Drift penalty (M14C Integration)
        drift = metrics.get('feature_drift', 0.0)
        if drift > 0.8:
            score -= 40
        elif drift > 0.3:
            score -= 15
            
        # 5. Execution Slippage penalty
        slippage = metrics.get('execution_slippage_bps', 0.0)
        if slippage > 5.0: # Highly subjective, depends on strategy frequency
            score -= 20
            
        # Ensure bounds
        return max(0.0, min(100.0, score))
