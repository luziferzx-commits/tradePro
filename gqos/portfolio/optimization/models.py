from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Any
import hashlib
import json

@dataclass(frozen=True)
class ConstraintResult:
    is_valid: bool
    violations: List[str] = field(default_factory=list)

@dataclass(frozen=True)
class TargetPortfolio:
    # Maps symbol to target weight percentage (e.g. 0.15 for 15%)
    target_weights: Dict[str, Decimal]
    
    def calculate_hash(self) -> str:
        # Sort keys to ensure deterministic hash
        data = {k: str(v) for k, v in sorted(self.target_weights.items())}
        return hashlib.sha256(json.dumps(data).encode('utf-8')).hexdigest()

@dataclass(frozen=True)
class OptimizationProblem:
    expected_returns: Dict[str, Decimal]
    covariance_matrix: Dict[str, Dict[str, Decimal]]
    # Since interfaces cannot be easily serialized to JSON, we use their string representation
    # or class names for hash determinism.
    objective_function_name: str
    constraint_names: List[str]
    
    def calculate_hash(self) -> str:
        data = {
            "expected_returns": {k: str(v) for k, v in sorted(self.expected_returns.items())},
            "covariance_matrix": {k: {ik: str(iv) for ik, iv in sorted(v.items())} for k, v in sorted(self.covariance_matrix.items())},
            "objective_function": self.objective_function_name,
            "constraints": sorted(self.constraint_names)
        }
        return hashlib.sha256(json.dumps(data).encode('utf-8')).hexdigest()
