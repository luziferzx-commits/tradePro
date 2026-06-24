from typing import List

class OptimizationFailedError(Exception):
    pass

class ConstraintViolationError(Exception):
    def __init__(self, violations: List[str]):
        self.violations = violations
        super().__init__(f"Target Portfolio violated constraints: {violations}")
