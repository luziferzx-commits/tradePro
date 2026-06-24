from typing import List
from gqos.portfolio.optimization.interfaces import IConstraint
from gqos.portfolio.optimization.models import TargetPortfolio
from gqos.portfolio.optimization.exceptions import ConstraintViolationError

class AllocationValidator:
    def validate(self, target_portfolio: TargetPortfolio, constraints: List[IConstraint]) -> None:
        all_violations = []
        for constraint in constraints:
            result = constraint.validate(target_portfolio)
            if not result.is_valid:
                all_violations.extend(result.violations)
                
        if all_violations:
            raise ConstraintViolationError(all_violations)
