from decimal import Decimal
from typing import List, Dict, Callable
import copy
from gqos.portfolio.optimization.interfaces import IOptimizer, IConstraint, IObjectiveFunction
from gqos.portfolio.optimization.models import OptimizationProblem, TargetPortfolio
from gqos.portfolio.optimization.analytics.models import SensitivityResult

class SensitivityAnalyzer:
    def __init__(self, optimizer: IOptimizer):
        self.optimizer = optimizer

    def analyze_returns_sensitivity(
        self,
        problem: OptimizationProblem,
        constraints: List[IConstraint],
        objective: IObjectiveFunction,
        perturbation_func: Callable[[str, Decimal], Decimal]
    ) -> SensitivityResult:
        """
        Analyzes the sensitivity of the optimizer to changes in expected returns.
        """
        # Baseline optimization
        original_portfolio = self.optimizer.optimize(problem, constraints, objective)
        original_hash = original_portfolio.calculate_hash()
        
        # Create perturbed problem without mutating original
        perturbed_returns = {}
        for symbol, ret in problem.expected_returns.items():
            perturbed_returns[symbol] = perturbation_func(symbol, ret)
            
        perturbed_problem = OptimizationProblem(
            expected_returns=perturbed_returns,
            covariance_matrix=problem.covariance_matrix, # Keeping same object is fine since dataclass is frozen and we don't mutate
            objective_function_name=problem.objective_function_name,
            constraint_names=problem.constraint_names
        )
        
        # Perturbed optimization
        perturbed_portfolio = self.optimizer.optimize(perturbed_problem, constraints, objective)
        perturbed_hash = perturbed_portfolio.calculate_hash()
        
        # Calculate drift
        weight_drift_by_symbol: Dict[str, Decimal] = {}
        total_turnover = Decimal('0')
        
        all_symbols = set(original_portfolio.target_weights.keys()).union(set(perturbed_portfolio.target_weights.keys()))
        
        for symbol in all_symbols:
            orig_w = original_portfolio.target_weights.get(symbol, Decimal('0'))
            new_w = perturbed_portfolio.target_weights.get(symbol, Decimal('0'))
            drift = new_w - orig_w
            weight_drift_by_symbol[symbol] = drift
            total_turnover += abs(drift)
            
        # Turnover is usually sum(abs(delta)) / 2 for a full portfolio replacement
        # But we will just return the absolute sum of differences as 'total_turnover' for simplicity,
        # or divide by 2 if requested. The standard definition is sum(abs)/2.
        total_turnover = total_turnover / Decimal('2.0')
        
        return SensitivityResult(
            original_portfolio_hash=original_hash,
            perturbed_portfolio_hash=perturbed_hash,
            total_turnover=total_turnover,
            weight_drift_by_symbol=weight_drift_by_symbol
        )
