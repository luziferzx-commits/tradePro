from abc import ABC, abstractmethod
from typing import Dict, List
from gqos.portfolio.optimization.models import OptimizationProblem, TargetPortfolio, ConstraintResult

class IObjectiveFunction(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

class IConstraint(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def validate(self, target_portfolio: TargetPortfolio) -> ConstraintResult:
        """
        Validates if the generated portfolio weights satisfy this constraint.
        """
        pass

class IOptimizer(ABC):
    @abstractmethod
    def optimize(
        self, 
        problem: OptimizationProblem, 
        constraints: List[IConstraint], 
        objective: IObjectiveFunction
    ) -> TargetPortfolio:
        """
        Solves the optimization problem. Must be a pure, stateless function.
        """
        pass
