from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict

@dataclass(frozen=True)
class FactorExposureResult:
    # Portfolio's net exposure to each factor
    exposures: Dict[str, Decimal]

@dataclass(frozen=True)
class FactorReturnAttributionResult:
    total_return: Decimal
    factor_returns: Dict[str, Decimal]
    specific_return: Decimal # Alpha / idiosyncratic

@dataclass(frozen=True)
class DrawdownAttributionResult:
    total_drawdown_amount: Decimal
    total_drawdown_percent: Decimal
    contribution_by_strategy: Dict[str, Decimal]
    contribution_by_sector: Dict[str, Decimal]
    contribution_by_symbol: Dict[str, Decimal]
