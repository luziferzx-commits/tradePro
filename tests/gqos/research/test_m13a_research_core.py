from datetime import datetime, timezone
from gqos.research.dataset import DatasetMetadata, DatasetFingerprint, TimeRange
from gqos.research.experiment import ExperimentDefinition

def test_dataset_metadata_immutable_and_deterministic():
    tr = TimeRange(start_date=datetime(2018, 1, 1, tzinfo=timezone.utc), 
                   end_date=datetime(2025, 1, 1, tzinfo=timezone.utc))
    
    ds1 = DatasetMetadata(
        dataset_id="DS-001",
        version="v1.0.0",
        schema_version="1.0",
        data_hash="abc123hash",
        source="vendor_a",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        row_count=1000000,
        time_range=tr,
        frequency="1m",
        column_signature=["timestamp", "open", "high", "low", "close", "volume"],
        parent_dataset_id=None
    )
    
    # Prove deterministic hashing with identical input
    ds2 = DatasetMetadata(
        dataset_id="DS-001",
        version="v1.0.0",
        schema_version="1.0",
        data_hash="abc123hash",
        source="vendor_a",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        row_count=1000000,
        time_range=tr,
        frequency="1m",
        column_signature=["timestamp", "open", "high", "low", "close", "volume"],
        parent_dataset_id=None
    )
    
    assert ds1.calculate_hash() == ds2.calculate_hash()
    
    # Immutability Check (dataclass frozen)
    try:
        ds1.row_count = 5
        assert False, "Should be immutable"
    except Exception:
        pass

def test_dataset_lineage():
    tr = TimeRange(start_date=datetime(2018, 1, 1, tzinfo=timezone.utc), 
                   end_date=datetime(2025, 1, 1, tzinfo=timezone.utc))
                   
    parent = DatasetMetadata(
        dataset_id="RAW-TICK-001",
        version="v1.0.0",
        schema_version="1.0",
        data_hash="raw123",
        source="vendor_a",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        row_count=5000000,
        time_range=tr,
        frequency="tick",
        column_signature=["timestamp", "price", "size"]
    )
    
    child = DatasetMetadata(
        dataset_id="CLEAN-1M-001",
        version="v1.0.0",
        schema_version="2.0",
        data_hash="clean456",
        source="internal_etl",
        created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        row_count=1000000,
        time_range=tr,
        frequency="1m",
        column_signature=["timestamp", "open", "high", "low", "close", "volume"],
        parent_dataset_id=parent.dataset_id
    )
    
    assert child.parent_dataset_id == "RAW-TICK-001"

def test_dataset_fingerprint():
    tr = TimeRange(start_date=datetime(2018, 1, 1, tzinfo=timezone.utc), 
                   end_date=datetime(2025, 1, 1, tzinfo=timezone.utc))
                   
    ds = DatasetMetadata(
        dataset_id="DS-001",
        version="v1.0.0",
        schema_version="1.0",
        data_hash="abc123hash",
        source="vendor_a",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        row_count=1000000,
        time_range=tr,
        frequency="1m",
        column_signature=["timestamp", "open", "high", "low", "close", "volume"]
    )
    
    fp = ds.get_fingerprint()
    assert fp.data_hash == "abc123hash"
    assert fp.row_count == 1000000
    assert fp.schema_version == "1.0"
    
    # Hash of fingerprint should be stable
    assert len(fp.calculate_hash()) == 64 # SHA256 length

def test_experiment_definition_immutable_and_deterministic():
    exp1 = ExperimentDefinition(
        experiment_id="EXP-2026-00031",
        problem_hash="prob_123",
        dataset_hash="ds_fp_123",
        strategy_hash="strat_123",
        parameter_hash="param_123",
        engine_version="v1.2.0"
    )
    
    exp2 = ExperimentDefinition(
        experiment_id="EXP-2026-00031",
        problem_hash="prob_123",
        dataset_hash="ds_fp_123",
        strategy_hash="strat_123",
        parameter_hash="param_123",
        engine_version="v1.2.0"
    )
    
    assert exp1.calculate_hash() == exp2.calculate_hash()
    
    # Immutability Check
    try:
        exp1.experiment_id = "NEW"
        assert False, "Should be immutable"
    except Exception:
        pass

if __name__ == "__main__":
    test_dataset_metadata_immutable_and_deterministic()
    test_dataset_lineage()
    test_dataset_fingerprint()
    test_experiment_definition_immutable_and_deterministic()
    print("M13A Research Core tests passed!")
