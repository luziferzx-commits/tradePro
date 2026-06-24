from dataclasses import dataclass
from typing import Dict, List, Any
import hashlib
import json

from gqos.research.experiment import ExperimentDefinition
from gqos.research.walk_forward.models import FoldManifest
from gqos.research.walk_forward.interfaces import EvaluationResult

@dataclass(frozen=True)
class StrategyCard:
    purpose: str
    markets: List[str]
    timeframe: str
    factor_exposure: Dict[str, str]
    known_failure_modes: List[str]
    walk_forward_metrics: Dict[str, str]
    risk_metrics: Dict[str, str]
    data_version: str
    optimizer_version: str
    researcher: str
    approval_status: str

    def calculate_hash(self) -> str:
        data = {
            "purpose": self.purpose,
            "markets": sorted(self.markets),
            "timeframe": self.timeframe,
            "factor_exposure": self.factor_exposure,
            "known_failure_modes": sorted(self.known_failure_modes),
            "walk_forward_metrics": self.walk_forward_metrics,
            "risk_metrics": self.risk_metrics,
            "data_version": self.data_version,
            "optimizer_version": self.optimizer_version,
            "researcher": self.researcher,
            "approval_status": self.approval_status
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()

@dataclass(frozen=True)
class ExperimentResult:
    definition: ExperimentDefinition
    fold_manifest: FoldManifest
    evaluation_results: List[EvaluationResult]

    def calculate_hash(self) -> str:
        # Convert to a dictionary that is easily serializable for hashing
        data = {
            "definition_hash": self.definition.calculate_hash(),
            "fold_manifest_hash": self.fold_manifest.calculate_hash(),
            "evaluations": [res.artifact_hash for res in self.evaluation_results]
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()

@dataclass(frozen=True)
class ResearchManifest:
    dataset_hash: str
    experiment_id: str
    result_hash: str
    card_hash: str

    def calculate_hash(self) -> str:
        data = {
            "dataset_hash": self.dataset_hash,
            "experiment_id": self.experiment_id,
            "result_hash": self.result_hash,
            "card_hash": self.card_hash
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()
