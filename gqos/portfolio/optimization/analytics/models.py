from dataclasses import dataclass
from decimal import Decimal
from typing import Dict
from gqos.portfolio.optimization.models import TargetPortfolio

@dataclass(frozen=True)
class SensitivityResult:
    original_portfolio_hash: str
    perturbed_portfolio_hash: str
    total_turnover: Decimal
    weight_drift_by_symbol: Dict[str, Decimal]
