from decimal import Decimal
from typing import Dict
from gqos.portfolio.optimization.interfaces import IConstraint
from gqos.portfolio.optimization.models import TargetPortfolio, ConstraintResult

class MaxWeightConstraint(IConstraint):
    def __init__(self, max_weight: Decimal):
        self._max_weight = max_weight

    @property
    def name(self) -> str:
        return f"MaxWeightConstraint({self._max_weight})"

    def validate(self, target_portfolio: TargetPortfolio) -> ConstraintResult:
        violations = []
        for symbol, weight in target_portfolio.target_weights.items():
            if weight > self._max_weight:
                violations.append(f"Symbol {symbol} weight {weight} exceeds max {self._max_weight}")
        
        return ConstraintResult(is_valid=len(violations) == 0, violations=violations)

class SumToOneConstraint(IConstraint):
    def __init__(self, tolerance: Decimal = Decimal('0.0001')):
        self._tolerance = tolerance

    @property
    def name(self) -> str:
        return f"SumToOneConstraint(tol={self._tolerance})"

    def validate(self, target_portfolio: TargetPortfolio) -> ConstraintResult:
        total_weight = sum(target_portfolio.target_weights.values())
        diff = abs(Decimal('1.0') - total_weight)
        
        if diff <= self._tolerance:
            return ConstraintResult(is_valid=True)
        else:
            return ConstraintResult(is_valid=False, violations=[f"Sum of weights is {total_weight}, diff {diff} exceeds tolerance {self._tolerance}"])

class SectorWeightConstraint(IConstraint):
    def __init__(self, max_sector_weight: Decimal, symbol_to_sector: Dict[str, str]):
        self._max_sector_weight = max_sector_weight
        self._symbol_to_sector = symbol_to_sector

    @property
    def name(self) -> str:
        return f"SectorWeightConstraint(max={self._max_sector_weight})"

    def validate(self, target_portfolio: TargetPortfolio) -> ConstraintResult:
        sector_weights: Dict[str, Decimal] = {}
        for symbol, weight in target_portfolio.target_weights.items():
            sector = self._symbol_to_sector.get(symbol, "UNKNOWN")
            sector_weights[sector] = sector_weights.get(sector, Decimal('0')) + weight
            
        violations = []
        for sector, total_weight in sector_weights.items():
            if total_weight > self._max_sector_weight:
                violations.append(f"Sector {sector} weight {total_weight} exceeds max {self._max_sector_weight}")
                
        return ConstraintResult(is_valid=len(violations) == 0, violations=violations)
