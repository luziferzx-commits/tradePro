from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

from gqos.research.dataset import TimeRange
from gqos.research.walk_forward.models import WalkForwardFold, FoldManifest
from gqos.research.walk_forward.exceptions import DataLeakageError
from gqos.research.walk_forward.generator import WalkForwardGenerator

def test_timerange_and_fold_immutability():
    tr = TimeRange(start_date=datetime(2020, 1, 1, tzinfo=timezone.utc), end_date=datetime(2021, 1, 1, tzinfo=timezone.utc))
    try:
        tr.start_date = datetime(2022, 1, 1, tzinfo=timezone.utc)
        assert False, "Should be immutable"
    except Exception:
        pass
        
    fold = WalkForwardFold(dataset_hash="hash1", train_window=tr, test_window=tr)
    try:
        fold.dataset_hash = "hash2"
        assert False, "Should be immutable"
    except Exception:
        pass

def test_fold_id_deterministic():
    tr1 = TimeRange(start_date=datetime(2020, 1, 1, tzinfo=timezone.utc), end_date=datetime(2021, 1, 1, tzinfo=timezone.utc))
    tr2 = TimeRange(start_date=datetime(2021, 1, 1, tzinfo=timezone.utc), end_date=datetime(2022, 1, 1, tzinfo=timezone.utc))
    
    fold1 = WalkForwardFold(dataset_hash="hash1", train_window=tr1, test_window=tr2)
    fold2 = WalkForwardFold(dataset_hash="hash1", train_window=tr1, test_window=tr2)
    
    assert fold1.fold_id == fold2.fold_id
    
    # Change dataset hash -> changes fold_id
    fold3 = WalkForwardFold(dataset_hash="hash2", train_window=tr1, test_window=tr2)
    assert fold1.fold_id != fold3.fold_id

def test_leakage_overlap_train_test():
    # Train ends 2021-02-01, Test starts 2021-01-01 (Overlap!)
    train_w = TimeRange(start_date=datetime(2020, 1, 1, tzinfo=timezone.utc), end_date=datetime(2021, 2, 1, tzinfo=timezone.utc))
    test_w = TimeRange(start_date=datetime(2021, 1, 1, tzinfo=timezone.utc), end_date=datetime(2021, 6, 1, tzinfo=timezone.utc))
    
    fold = WalkForwardFold(dataset_hash="hash", train_window=train_w, test_window=test_w)
    
    try:
        fold.validate_leakage()
        assert False, "Should have raised DataLeakageError"
    except DataLeakageError as e:
        assert "overlaps with Test window" in str(e)

def test_leakage_gap_enforced():
    # Gap overlaps with Train
    train_w = TimeRange(start_date=datetime(2020, 1, 1, tzinfo=timezone.utc), end_date=datetime(2021, 1, 15, tzinfo=timezone.utc))
    gap_w = TimeRange(start_date=datetime(2021, 1, 1, tzinfo=timezone.utc), end_date=datetime(2021, 2, 1, tzinfo=timezone.utc))
    test_w = TimeRange(start_date=datetime(2021, 2, 1, tzinfo=timezone.utc), end_date=datetime(2021, 6, 1, tzinfo=timezone.utc))
    
    fold = WalkForwardFold(dataset_hash="hash", train_window=train_w, gap_window=gap_w, test_window=test_w)
    try:
        fold.validate_leakage()
        assert False, "Should have raised DataLeakageError"
    except DataLeakageError as e:
        assert "Train window overlaps with Gap window" in str(e)

def test_generator_rolling_folds():
    gen = WalkForwardGenerator("data_hash_123")
    master = TimeRange(start_date=datetime(2020, 1, 1, tzinfo=timezone.utc), end_date=datetime(2020, 7, 1, tzinfo=timezone.utc))
    
    manifest = gen.generate_rolling_folds(
        master_window=master,
        train_duration=relativedelta(months=2),
        test_duration=relativedelta(months=1),
        gap_duration=relativedelta(days=5)
    )
    
    assert len(manifest.folds) == 3
    
    # Fold 1
    f1 = manifest.folds[0]
    assert f1.train_window.start_date == datetime(2020, 1, 1, tzinfo=timezone.utc)
    assert f1.train_window.end_date == datetime(2020, 3, 1, tzinfo=timezone.utc)
    assert f1.gap_window.start_date == datetime(2020, 3, 1, tzinfo=timezone.utc)
    assert f1.gap_window.end_date == datetime(2020, 3, 6, tzinfo=timezone.utc)
    assert f1.test_window.start_date == datetime(2020, 3, 6, tzinfo=timezone.utc)
    assert f1.test_window.end_date == datetime(2020, 4, 6, tzinfo=timezone.utc)
    
    # Fold 2 (Slide by test duration = 1 month)
    f2 = manifest.folds[1]
    assert f2.train_window.start_date == datetime(2020, 2, 1, tzinfo=timezone.utc)
    assert f2.train_window.end_date == datetime(2020, 4, 1, tzinfo=timezone.utc)

def test_generator_expanding_folds():
    gen = WalkForwardGenerator("data_hash_123")
    master = TimeRange(start_date=datetime(2020, 1, 1, tzinfo=timezone.utc), end_date=datetime(2020, 7, 1, tzinfo=timezone.utc))
    
    manifest = gen.generate_expanding_folds(
        master_window=master,
        initial_train_duration=relativedelta(months=2),
        test_duration=relativedelta(months=1)
    )
    
    assert len(manifest.folds) == 4
    
    # Anchored start
    for f in manifest.folds:
        assert f.train_window.start_date == datetime(2020, 1, 1, tzinfo=timezone.utc)
        
    assert manifest.folds[0].train_window.end_date == datetime(2020, 3, 1, tzinfo=timezone.utc)
    assert manifest.folds[1].train_window.end_date == datetime(2020, 4, 1, tzinfo=timezone.utc)
    assert manifest.folds[2].train_window.end_date == datetime(2020, 5, 1, tzinfo=timezone.utc)

def test_deterministic_repeated_generation_and_hash():
    gen = WalkForwardGenerator("data_hash_123")
    master = TimeRange(start_date=datetime(2020, 1, 1, tzinfo=timezone.utc), end_date=datetime(2020, 7, 1, tzinfo=timezone.utc))
    
    m1 = gen.generate_rolling_folds(master, relativedelta(months=2), relativedelta(months=1))
    m2 = gen.generate_rolling_folds(master, relativedelta(months=2), relativedelta(months=1))
    
    assert m1.calculate_hash() == m2.calculate_hash()
    assert len(m1.calculate_hash()) == 64

if __name__ == "__main__":
    test_timerange_and_fold_immutability()
    test_fold_id_deterministic()
    test_leakage_overlap_train_test()
    test_leakage_gap_enforced()
    test_generator_rolling_folds()
    test_generator_expanding_folds()
    test_deterministic_repeated_generation_and_hash()
    print("M13B Walk Forward Orchestration tests passed!")
