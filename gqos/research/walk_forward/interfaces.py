from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict

from gqos.research.experiment import ExperimentDefinition
from gqos.research.walk_forward.models import WalkForwardFold

@dataclass(frozen=True)
class EvaluationResult:
    fold_id: str
    experiment_id: str
    metrics: Dict[str, Decimal]
    equity_curve: Dict[datetime, Decimal]
    artifact_hash: str

class IStrategyEvaluator(ABC):
    @abstractmethod
    def evaluate(self, experiment: ExperimentDefinition, fold: WalkForwardFold) -> EvaluationResult:
        """
        Executes a backtest over the provided fold.
        """
        pass
