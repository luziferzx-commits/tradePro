from typing import List
from abc import ABC, abstractmethod

from gqos.research.factory.generators import TemplateAlpha

class AlphaConstraintRejection(Exception):
    pass

class IConstraint(ABC):
    @abstractmethod
    def evaluate(self, alpha: TemplateAlpha, backtest_metrics: dict):
        """
        Evaluates the generated Alpha against a constraint.
        Raises AlphaConstraintRejection if the constraint is violated.
        """
        pass

class TurnoverConstraint(IConstraint):
    def __init__(self, max_annual_turnover: float):
        self.max_annual_turnover = max_annual_turnover
        
    def evaluate(self, alpha: TemplateAlpha, backtest_metrics: dict):
        turnover = backtest_metrics.get("annual_turnover", 0.0)
        if turnover > self.max_annual_turnover:
            raise AlphaConstraintRejection(f"Turnover {turnover} exceeds max limit of {self.max_annual_turnover}")

class LiquidityConstraint(IConstraint):
    def __init__(self, required_liquidity_tier: str):
        self.required_liquidity_tier = required_liquidity_tier
        
    def evaluate(self, alpha: TemplateAlpha, backtest_metrics: dict):
        if alpha.metadata.liquidity_requirement != self.required_liquidity_tier:
             raise AlphaConstraintRejection(f"Alpha targets {alpha.metadata.liquidity_requirement}, but constraint requires {self.required_liquidity_tier}")

class CapacityConstraint(IConstraint):
    def __init__(self, min_capacity: float):
        self.min_capacity = min_capacity
        
    def evaluate(self, alpha: TemplateAlpha, backtest_metrics: dict):
        if alpha.metadata.estimated_capacity < self.min_capacity:
             raise AlphaConstraintRejection(f"Alpha capacity {alpha.metadata.estimated_capacity} is below minimum requirement {self.min_capacity}")

class ConstraintEngine:
    def __init__(self):
        self.constraints: List[IConstraint] = []
        
    def add_constraint(self, constraint: IConstraint):
        self.constraints.append(constraint)
        
    def filter(self, alphas: List[TemplateAlpha], metrics_map: dict) -> List[TemplateAlpha]:
        survivors = []
        for alpha in alphas:
            metrics = metrics_map.get(alpha.alpha_id, {})
            rejected = False
            for c in self.constraints:
                try:
                    c.evaluate(alpha, metrics)
                except AlphaConstraintRejection:
                    rejected = True
                    break
            
            if not rejected:
                survivors.append(alpha)
                
        return survivors
