from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import hashlib
import json

@dataclass(frozen=True)
class TimeRange:
    start_date: datetime
    end_date: datetime

@dataclass(frozen=True)
class DatasetFingerprint:
    data_hash: str
    row_count: int
    schema_version: str
    column_signature: List[str]
    
    def calculate_hash(self) -> str:
        data = {
            "data_hash": self.data_hash,
            "row_count": self.row_count,
            "schema_version": self.schema_version,
            "column_signature": sorted(self.column_signature)
        }
        return hashlib.sha256(json.dumps(data).encode('utf-8')).hexdigest()

@dataclass(frozen=True)
class DatasetMetadata:
    dataset_id: str
    version: str
    schema_version: str
    data_hash: str
    source: str
    created_at: datetime
    
    row_count: int
    time_range: TimeRange
    frequency: str
    column_signature: List[str]
    
    parent_dataset_id: Optional[str] = None
    
    def get_fingerprint(self) -> DatasetFingerprint:
        return DatasetFingerprint(
            data_hash=self.data_hash,
            row_count=self.row_count,
            schema_version=self.schema_version,
            column_signature=self.column_signature
        )

    def calculate_hash(self) -> str:
        data = {
            "dataset_id": self.dataset_id,
            "version": self.version,
            "schema_version": self.schema_version,
            "data_hash": self.data_hash,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "row_count": self.row_count,
            "time_range": {
                "start": self.time_range.start_date.isoformat(),
                "end": self.time_range.end_date.isoformat()
            },
            "frequency": self.frequency,
            "column_signature": sorted(self.column_signature),
            "parent_dataset_id": self.parent_dataset_id
        }
        return hashlib.sha256(json.dumps(data).encode('utf-8')).hexdigest()
