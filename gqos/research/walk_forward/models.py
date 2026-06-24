from dataclasses import dataclass
from typing import Optional, List
import hashlib
import json
from gqos.research.dataset import TimeRange
from gqos.research.walk_forward.exceptions import DataLeakageError

@dataclass(frozen=True)
class WalkForwardFold:
    dataset_hash: str
    train_window: TimeRange
    test_window: TimeRange
    gap_window: Optional[TimeRange] = None

    @property
    def fold_id(self) -> str:
        data = {
            "dataset_hash": self.dataset_hash,
            "train": {"start": self.train_window.start_date.isoformat(), "end": self.train_window.end_date.isoformat()},
            "test": {"start": self.test_window.start_date.isoformat(), "end": self.test_window.end_date.isoformat()},
            "gap": {"start": self.gap_window.start_date.isoformat(), "end": self.gap_window.end_date.isoformat()} if self.gap_window else None
        }
        return hashlib.sha256(json.dumps(data).encode('utf-8')).hexdigest()

    def validate_leakage(self) -> None:
        """
        Validates that Train and Test do not overlap, and that the Gap is respected.
        Raises DataLeakageError if leakage is detected.
        """
        # TimeRange logic: start <= end
        if self.train_window.start_date > self.train_window.end_date:
            raise DataLeakageError("Train window start date must be before end date")
        if self.test_window.start_date > self.test_window.end_date:
            raise DataLeakageError("Test window start date must be before end date")

        if self.gap_window:
            # Check gap logic: train_end <= gap_start <= gap_end <= test_start
            if not (self.train_window.end_date <= self.gap_window.start_date):
                raise DataLeakageError("Train window overlaps with Gap window")
            if not (self.gap_window.start_date <= self.gap_window.end_date):
                raise DataLeakageError("Gap window start date must be before end date")
            if not (self.gap_window.end_date <= self.test_window.start_date):
                raise DataLeakageError("Gap window overlaps with Test window")
        else:
            # No gap: train_end <= test_start
            if not (self.train_window.end_date <= self.test_window.start_date):
                raise DataLeakageError("Train window overlaps with Test window")

@dataclass(frozen=True)
class FoldManifest:
    folds: List[WalkForwardFold]
    
    def calculate_hash(self) -> str:
        data = [f.fold_id for f in self.folds]
        return hashlib.sha256(json.dumps(data).encode('utf-8')).hexdigest()
