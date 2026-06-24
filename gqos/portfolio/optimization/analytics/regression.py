from typing import List
from gqos.portfolio.optimization.interfaces import IOptimizer, IConstraint, IObjectiveFunction
from gqos.portfolio.optimization.models import OptimizationProblem, TargetPortfolio
from gqos.portfolio.optimization.analytics.exceptions import RegressionDriftDetectedError

class OptimizerRegressionHarness:
    def __init__(self, optimizer: IOptimizer):
        self.optimizer = optimizer

    def assert_regression_baseline(
        self,
        problem: OptimizationProblem,
        constraints: List[IConstraint],
        objective: IObjectiveFunction,
        expected_portfolio_hash: str
    ) -> TargetPortfolio:
        """
        Runs the optimizer and asserts that the resulting TargetPortfolio hash
        perfectly matches the known deterministic baseline.
        """
        portfolio = self.optimizer.optimize(problem, constraints, objective)
        actual_hash = portfolio.calculate_hash()
        
        if actual_hash != expected_portfolio_hash:
            raise RegressionDriftDetectedError(
                expected_hash=expected_portfolio_hash,
                actual_hash=actual_hash
            )
            
        return portfolio
