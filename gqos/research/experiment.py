from dataclasses import dataclass, field
from typing import Dict, Optional
import hashlib
import json
import time
import psutil

@dataclass
class ResearchCost:
    cpu_time_seconds: float = 0.0
    gpu_time_seconds: float = 0.0
    peak_ram_mb: float = 0.0

@dataclass
class DatasetVersion:
    name: str
    hash: str
    semantic_version: str # e.g., v1.3.2

@dataclass
class ExperimentIdentity:
    experiment_id: str # e.g., EXP-2026-0001
    run_id: str # e.g., RUN-0012
    trial_id: str # e.g., TRIAL-0834

@dataclass(frozen=True)
class ExperimentDefinition:
    experiment_id: str
    problem_hash: str     # Hypothesis / Problem formulation hash
    dataset_hash: str     # Resolves to DatasetFingerprint.calculate_hash()
    strategy_hash: str    # Identifies the exact strategy code / logic
    parameter_hash: str   # Identifies the hyperparameter space used
    engine_version: str   # Version of the GQOS execution engine used
    
    def calculate_hash(self) -> str:
        data = {
            "experiment_id": self.experiment_id,
            "problem_hash": self.problem_hash,
            "dataset_hash": self.dataset_hash,
            "strategy_hash": self.strategy_hash,
            "parameter_hash": self.parameter_hash,
            "engine_version": self.engine_version
        }
        return hashlib.sha256(json.dumps(data).encode('utf-8')).hexdigest()

class ExperimentTracker:
    def __init__(self, exp_id: str):
        self.experiment_id = exp_id
        self._start_time = 0.0
        self.run_id = ""
        
    def start_run(self, run_id: str):
        self._start_time = time.time()
        self.run_id = run_id
        
    def end_run(self) -> ResearchCost:
        elapsed = time.time() - self._start_time
        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024 * 1024)
        
        return ResearchCost(
            cpu_time_seconds=elapsed,
            gpu_time_seconds=0.0,
            peak_ram_mb=memory_mb
        )
